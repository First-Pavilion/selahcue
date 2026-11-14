#!/usr/bin/env python3
"""Build a non-NDI Ubuntu release candidate; never embed keys or publish downloads."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from installer_secret_scan import MIN_ARTEFACT_BYTES, SIGNATURES, ScanError, run_scan
from ubuntu_packaging_preflight import OPERATOR, TARGET, elf_problem
from whisper_cpu_policy import PolicyError, file_sha, operator_environment, require_fresh_target, verify


class PackagingError(RuntimeError):
    pass


def merge_patch(target, patch):
    """RFC7396, matching pinned tauri-utils::config::parse::read_from."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    result = copy.deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def effective_config(root: Path) -> dict:
    directory = root / OPERATOR
    base = json.loads((directory / "tauri.conf.json").read_text())
    overlay = json.loads((directory / "tauri.linux.conf.json").read_text())
    return merge_patch(base, overlay)


def validate_config(cfg: dict) -> None:
    bundle = cfg.get("bundle", {})
    if bundle.get("targets") != ["deb"] or bundle.get("resources") != []:
        raise PackagingError("Linux effective config must select only deb and replace Windows resources with an empty array")
    if bundle.get("externalBin") != ["binaries/selahcue-output"]:
        raise PackagingError("Linux package must declare the real audience output sidecar")


def build_environment(incoming: dict) -> dict:
    blocked = ("OPENAI_API_KEY", "DEEPGRAM_API_KEY", "RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS",
               "CARGO_BUILD_RUSTFLAGS", "CARGO_TARGET_DIR", "TAURI_CONFIG", "RUSTUP_TOOLCHAIN",
               "LD_LIBRARY_PATH", "LD_PRELOAD")
    prefixes = ("CARGO_PROFILE_", "CARGO_TARGET_", "NDI_", "DYLD_", "SELAHCUE_", "TAURI_")
    return {key: value for key, value in incoming.items()
            if key not in blocked and not key.startswith(prefixes)}


def build_commands(root: Path) -> tuple[list[str], list[str]]:
    sidecar = ["cargo", "build", "--manifest-path", str(root / "implementation/desktop/Cargo.toml"),
               "--release", "--target", TARGET, "-p", "selahcue-desktop", "--locked",
               "--message-format=json-render-diagnostics"]
    operator = ["cargo", "tauri", "build", "--target", TARGET, "--bundles", "deb",
                "--features", "stt", "--ci", "--", "--locked"]
    return sidecar, operator


def stage_sidecar(source: Path, destination: Path, *, debug_assertions: bool) -> None:
    if debug_assertions is not False:
        raise PackagingError("Cargo must identify the emitted sidecar as a release build without debug assertions")
    problem = elf_problem(source)
    if problem or source.stat().st_size < MIN_ARTEFACT_BYTES:
        raise PackagingError("Sidecar is absent, placeholder, truncated or not x86_64 ELF")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755)


def require_fresh_bundle_directory(directory: Path) -> None:
    if directory.exists() and any(directory.iterdir()):
        raise PackagingError("Debian output directory is not empty; use a fresh worktree/target directory")


def select_deb(directory: Path) -> Path:
    packages = list(directory.glob("*.deb"))
    if len(packages) != 1:
        raise PackagingError(f"Expected exactly one freshly built deb, found {len(packages)}")
    return packages[0]


def run(command: list[str], root: Path, env: dict, **kwargs):
    return subprocess.run(command, cwd=root, env=env, check=True, **kwargs)


def check_elf_closure(path: Path, root: Path, env: dict) -> dict:
    if elf_problem(path, executable=True):
        raise PackagingError("Package binary is not an executable x86_64 ELF")
    dynamic = run(["readelf", "-d", str(path)], root, env, capture_output=True, text=True).stdout
    linked = run(["ldd", str(path)], root, env, capture_output=True, text=True).stdout
    if "not found" in linked or "libndi" in (dynamic + linked).lower() or ".dll" in dynamic.lower():
        raise PackagingError("Package has unresolved, NDI or Windows runtime dependencies")
    # No development-tree RPATH/RUNPATH may substitute for system/package closure.
    for line in dynamic.splitlines():
        if ("RPATH" in line or "RUNPATH" in line) and (str(root) in line or "/Users/" in line or "/target/" in line):
            raise PackagingError("Package relies on a development-tree runtime search path")
    return {"binary": path.name, "readelf_dynamic": dynamic, "ldd": linked}


def scan_package(unpacked: Path, package: Path, main_name: str) -> None:
    copied = unpacked / "candidate.deb"
    shutil.copyfile(package, copied)
    targets = tuple((name, MIN_ARTEFACT_BYTES, name) for name in
                    (f"usr/bin/{main_name}", "usr/bin/selahcue-output", "candidate.deb"))
    run_scan(unpacked, targets, SIGNATURES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--inspect-config", action="store_true", help="validate/print Linux effective bundle without building")
    args = parser.parse_args()
    root = args.root.resolve()
    op = root / OPERATOR
    env = build_environment(dict(os.environ))
    cfg = effective_config(root)
    validate_config(cfg)
    if args.inspect_config:
        print(json.dumps({"bundle": cfg["bundle"], "public_download_ready": False}, indent=2))
        return 0
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise PackagingError("Build this candidate natively on Ubuntu24.04 x86_64; cross-platform staging is not packaging proof")
    release = Path("/etc/os-release").read_text()
    if 'ID=ubuntu' not in release or 'VERSION_ID="24.04"' not in release:
        raise PackagingError("This candidate is pinned to Ubuntu24.04")
    run(["sh", "scripts/check_toolchain.sh"], root, env)
    sidecar_cmd, operator_cmd = build_commands(root)
    # Cargo records the executable THIS invocation emitted; no stale-target glob.
    with tempfile.TemporaryFile(mode="w+") as messages:
        run(sidecar_cmd, root, env, stdout=messages)
        messages.seek(0)
        emitted = []
        for line in messages:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if (message.get("reason") == "compiler-artifact" and
                    message.get("target", {}).get("name") == "selahcue-output" and message.get("executable")):
                emitted.append(message)
        if len(emitted) != 1:
            raise PackagingError("Cargo did not identify exactly one real output executable")
        source = Path(emitted[0]["executable"]).resolve()
        if not source.is_relative_to(root / "implementation/desktop/target"):
            raise PackagingError("Output artifact was emitted outside this checkout's target directory")
        staged = op / f"binaries/selahcue-output-{TARGET}"
        stage_sidecar(source, staged, debug_assertions=emitted[0].get("profile", {}).get("debug_assertions"))
    operator_target = root / ".target" / "portable-linux"
    require_fresh_target(operator_target)
    operator_env = operator_environment(env, "linux", operator_target)
    bundle_dir = operator_target / TARGET / "release/bundle/deb"
    require_fresh_bundle_directory(bundle_dir)
    run(operator_cmd, op, operator_env)
    whisper_receipt = verify(operator_target, "linux", target_triple=TARGET)
    package = select_deb(bundle_dir)
    main_name = cfg.get("mainBinaryName", "selahcue-operator")
    if not isinstance(main_name, str) or Path(main_name).name != main_name:
        raise PackagingError("Unexpected main binary name in effective config")
    output = (args.output or root / "dist/linux").resolve()
    if output.exists() and any(output.iterdir()):
        raise PackagingError("Output directory must be empty to avoid mixing release candidates")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="selahcue-deb-") as unpack:
        unpacked = Path(unpack)
        run(["dpkg-deb", "--extract", str(package), str(unpacked)], root, env)
        operator = unpacked / "usr/bin" / main_name
        sidecar = unpacked / "usr/bin/selahcue-output"
        if not operator.is_file() or not sidecar.is_file():
            raise PackagingError("Debian payload must install both operator and output into /usr/bin")
        if file_sha(sidecar) != file_sha(staged):
            raise PackagingError("Bundled sidecar differs from the release executable just staged")
        binaries = [operator, sidecar]
        closure = [check_elf_closure(path, root, env) for path in binaries]
        if list(unpacked.rglob("*.dll")) or list(unpacked.rglob("libndi*")):
            raise PackagingError("Non-NDI Linux package contains a Windows/NDI resource")
        # Reuse the exact existing marker policy and per-artifact positive controls.
        scan_package(unpacked, package, main_name)
        control = run(["dpkg-deb", "--field", str(package)], root, env, capture_output=True, text=True).stdout
        fields = dict(line.split(":", 1) for line in control.splitlines()
                      if line and not line[0].isspace() and ":" in line)
        fields = {key: value.strip() for key, value in fields.items()}
        if fields.get("Architecture") != "amd64" or not fields.get("Version") or not fields.get("Package"):
            raise PackagingError("Debian metadata must identify an amd64 package with version and package identity")
        sha = run(["git", "rev-parse", "HEAD"], root, env, capture_output=True, text=True).stdout.strip()
        metadata = {"source_sha": sha, "target": TARGET, "os": "Ubuntu24.04", "package": package.name,
                    "version": fields["Version"], "architecture": fields["Architecture"], "package_id": fields["Package"],
                    "sha256": file_sha(package), "size": package.stat().st_size,
                    "profile": "ordinary-release-no-ndi-with-local-stt", "main_binary": main_name, "signed": False,
                    "public_download_ready": False, "pilot_credentials_embedded": False,
                    "runtime_validation": "not-run-by-build", "control": control, "elf": closure}
        whisper_receipt["installer_sha256"] = metadata["sha256"]
        metadata["whisper_cpu_policy"] = whisper_receipt
        for key in ("GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            if key in env:
                metadata[key.lower()] = env[key]
        shutil.copyfile(package, output / package.name)
        (output / "release-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        (output / "SHA256SUMS").write_text(f"{metadata['sha256']}  {package.name}\n")
    print("Built and inspected one ordinary Linux candidate; runtime and pilot readiness remain separate.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (PackagingError, PolicyError, ScanError, OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        # No environment values or scanned binary context in diagnostics.
        print(f"Linux packaging failed: {error}", file=sys.stderr)
        sys.exit(1)
