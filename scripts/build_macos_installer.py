#!/usr/bin/env python3
"""Build a local-STT, universal macOS DMG with portable Whisper CPU kernels."""
from __future__ import annotations

import argparse
import filecmp
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ARCHITECTURES = {"aarch64-apple-darwin": "arm64", "x86_64-apple-darwin": "x86_64"}
PORTABLE_WHISPER = dict.fromkeys(
    ("GGML_NATIVE", "GGML_SSE42", "GGML_AVX", "GGML_AVX2", "GGML_BMI2", "GGML_FMA", "GGML_F16C"),
    "OFF",
)
RPATH_FLAG = "-C link-arg=-Wl,-rpath,@executable_path/../Frameworks"
TAURI_VERSION = "tauri-cli 2.12.4"
DMG_NAME = "SelahCue Operator_0.1.0_universal.dmg"


class PackagingError(RuntimeError):
    pass


def build_environment(sdk: Path, *, operator_target_dir: Path | None = None) -> dict[str, str]:
    # Derive the tool paths from the actual account home. Keep invocation-specific
    # state and provider, compiler, loader and signing overrides out of Cargo.
    home = Path.home()
    env = {
        "HOME": str(home),
        "PATH": f"{home}/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "TMPDIR": "/private/tmp",
        "CARGO_BUILD_JOBS": "1",
        "MACOSX_DEPLOYMENT_TARGET": "13.0",
        "NDI_SDK_DIR": str(sdk),
        "RUSTFLAGS": RPATH_FLAG,
    }
    if operator_target_dir is not None:
        env.update(PORTABLE_WHISPER, CARGO_TARGET_DIR=str(operator_target_dir), CI="true")
    return env


def architectures(binary: Path) -> set[str]:
    return set(subprocess.check_output(["/usr/bin/lipo", "-archs", str(binary)], text=True).split())


def sidecar_artifact(receipt: str, target_dir: Path, target: str) -> Path:
    artifacts = []
    for line in receipt.splitlines():
        item = json.loads(line)
        if (item["reason"] == "compiler-artifact" and item["target"]["name"] == "selahcue-output"
                and "bin" in item["target"]["kind"] and item.get("executable")):
            artifacts.append(item)
    if len(artifacts) != 1:
        raise PackagingError(f"Expected one release selahcue-output from Cargo for {target}")
    artifact = artifacts[0]
    if artifact.get("fresh") is not False or artifact.get("profile", {}).get("debug_assertions") is not False:
        raise PackagingError(f"Cargo did not compile a current release selahcue-output for {target}")
    binary = Path(artifact["executable"]).resolve()
    if binary != (target_dir / target / "release/selahcue-output").resolve() or not binary.is_file():
        raise PackagingError(f"Cargo emitted selahcue-output outside the expected {target} release path")
    arch = ARCHITECTURES[target]
    if architectures(binary) != {arch}:
        raise PackagingError(f"Cargo emitted selahcue-output without the expected single {arch} slice")
    return binary


def check_whisper_flags(target_dir: Path) -> dict[str, str]:
    receipts = {}
    for target, arch in ARCHITECTURES.items():
        release = target_dir / target / "release"
        caches = list(release.glob("build/whisper-rs-sys-*/out/build/CMakeCache.txt"))
        if len(caches) != 1:
            raise PackagingError(f"Expected one Whisper CMake cache for {arch}, found {len(caches)}")
        cache = caches[0]
        entries = dict(re.findall(r"^([^#\s/:=]+):[^=\n]+=(.*)$", cache.read_text(), re.MULTILINE))
        required = {"CMAKE_OSX_ARCHITECTURES": arch, **PORTABLE_WHISPER}
        for key, value in required.items():
            if entries.get(key) != value:
                raise PackagingError(f"{arch} Whisper CMake cache expected {key}={value}")
        cpu_flags = cache.parent / "ggml/src/CMakeFiles/ggml-cpu.dir/flags.make"
        if not cpu_flags.is_file():
            raise PackagingError(f"Whisper CMake compiler flags are missing for {arch}")
        flags = cpu_flags.read_text()
        for language in ("C", "CXX"):
            match = re.search(rf"^{language}_FLAGS\s*=\s*(.*)$", flags, re.MULTILINE)
            arguments = match[1].split() if match else []
            arch_flags = [value for flag, value in zip(arguments, arguments[1:]) if flag == "-arch"]
            if arch_flags != [arch]:
                raise PackagingError(f"Whisper {language} compiler flags do not select exactly the {arch} target")
            for flag in arguments:
                if re.fullmatch(r"-m(arch|cpu|tune)=.*|-m(avx.*|sse4.*|f16c|fma|bmi.*|amx.*)", flag):
                    raise PackagingError(f"{arch} Whisper {language} compiler flags contain {flag}")
        receipts[arch] = "\n".join(f"{key}={entries[key]}" for key in required) + "\n" + flags
    return receipts


def require_new_file(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise PackagingError(f"Output already exists at {path}")


def publish_dmg(package: Path, candidate: Path) -> None:
    require_new_file(candidate)
    with tempfile.NamedTemporaryFile(dir=candidate.parent, prefix=f".{candidate.name}.", suffix=".partial") as temporary:
        copied = Path(temporary.name)
        shutil.copy2(package, copied)
        if not filecmp.cmp(package, copied, shallow=False):
            raise PackagingError("Copied DMG does not match the completed Tauri image")
        # A same-directory hard link exposes the complete file atomically and
        # fails if another invocation published to the same name first.
        try:
            os.link(copied, candidate)
        except FileExistsError as exc:
            raise PackagingError(f"Output already exists at {candidate}") from exc


def run(command: list[str], directory: Path, env: dict[str, str], receipt: Path) -> Path:
    stdout = receipt.with_suffix(".stdout")
    stderr = receipt.with_suffix(".stderr")
    print(f"Running {command[0]} {command[1] if len(command) > 1 else ''}. Logs: {receipt}.*", flush=True)
    with stdout.open("w") as out, stderr.open("w") as err:
        try:
            subprocess.run(command, cwd=directory, env=env, check=True, stdout=out, stderr=err)
        except subprocess.CalledProcessError as exc:
            raise PackagingError(f"Command exited {exc.returncode}. See {stderr} and {stdout}") from exc
    return stdout


def build_installer(root: Path, output: Path, cli: Path) -> Path:
    if platform.system() != "Darwin":
        raise PackagingError("The universal DMG must be built on macOS")
    desktop = root / "implementation/desktop"
    operator = desktop / "crates/selahcue-operator"
    sdk = desktop / "vendor/ndi/macos"
    env = build_environment(sdk)
    if subprocess.check_output([str(cli), "tauri", "--version"], env=env, text=True).strip() != TAURI_VERSION:
        raise PackagingError(f"Preflight requires {TAURI_VERSION}")
    if not (sdk / "include/Processing.NDI.Lib.h").is_file() or not (sdk / "lib/libndi.dylib").is_file():
        raise PackagingError("Stage the macOS NDI SDK under implementation/desktop/vendor/ndi/macos")
    if architectures(sdk / "lib/libndi.dylib") != set(ARCHITECTURES.values()):
        raise PackagingError("The NDI dylib must be universal")
    output.mkdir(parents=True, exist_ok=True)
    candidate = output / DMG_NAME
    require_new_file(candidate)
    work = output / "scratch"
    require_new_file(work)
    work.mkdir()
    target_dir = work / "target"
    stage = operator / "binaries"
    stage.mkdir(exist_ok=True)
    thin_binaries = []
    for target in ARCHITECTURES:
        receipt = run(
            ["cargo", "build", "--release", "--locked", "-p", "selahcue-desktop",
             "--bin", "selahcue-output", "--features", "ndi", "--target", target,
             "--target-dir", str(target_dir), "--message-format=json-render-diagnostics"],
            desktop, env, work / f"output-{target}",
        )
        artifact = sidecar_artifact(receipt.read_text(), target_dir, target)
        thin_binaries.append(str(artifact))
        shutil.copy2(artifact, stage / f"selahcue-output-{target}")
    universal = stage / "selahcue-output-universal-apple-darwin"
    lipo_output = work / universal.name
    subprocess.run(["/usr/bin/lipo", "-create", *thin_binaries, "-output", str(lipo_output)], check=True)
    if architectures(lipo_output) != set(ARCHITECTURES.values()):
        raise PackagingError("The staged sidecar must contain both slices")
    shutil.copy2(lipo_output, universal)

    operator_env = build_environment(sdk, operator_target_dir=target_dir)
    tauri = [str(cli), "tauri"]
    options = ["--target", "universal-apple-darwin", "--features", "stt", "--ci"]
    run([*tauri, "build", *options, "--no-bundle", "--", "--locked"], operator, operator_env, work / "tauri-build")
    for arch, receipt in check_whisper_flags(target_dir).items():
        (work / f"whisper-{arch}.txt").write_text(receipt)
    run([*tauri, "bundle", *options, "--bundles", "dmg"], operator, operator_env, work / "tauri-bundle")
    package = target_dir / "universal-apple-darwin/release/bundle/dmg" / DMG_NAME
    if not package.is_file() or package.stat().st_size == 0:
        raise PackagingError("Tauri did not produce the expected DMG")
    publish_dmg(package, candidate)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tauri", required=True, type=Path, help="path to the pinned cargo-tauri binary")
    parser.add_argument("--output", required=True, type=Path, help="directory for this DMG and build receipts")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        print(build_installer(root, args.output.resolve(), args.tauri.resolve()))
    except (PackagingError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Mac packaging failed. {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
