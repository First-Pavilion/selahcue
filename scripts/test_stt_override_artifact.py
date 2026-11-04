#!/usr/bin/env python3
"""Compile the real STT model selector, exercise it, and scan its native release bytes.

No GUI, model, microphone, provider or synthetic marker-bearing executable is run.
Mandatory full-scanner verdicts use separately built real native operator artifacts.
The small source-exact std-only probe is supplemental: its matcher checks prove LTO/
stripping behavior; the full gate MUST still reject it below the unchanged1MB floor.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile


EXPECTED_MARKER = "SELAHCUE_UNSAFE_STT_DEVELOPER_OVERRIDE_V1"
BINARY_NAME = "stt-override-effect-probe"
CASES = (
    ("normal_release", False, "table", "fat", {}),
    ("profile_assertions", True, "table", "fat", {}),
    ("inline_profile", True, "inline", "fat", {}),
    ("profile_environment", True, "table", "fat", {"CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS": "true"}),
    ("rustflags_valueless", True, "table", "fat", {"RUSTFLAGS": "-Cdebug-assertions"}),
    ("encoded_rustflags", True, "table", "fat", {"CARGO_ENCODED_RUSTFLAGS": "-C\x1fdebug-assertions=y"}),
    ("legacy_config", True, "legacy", "fat", {}),
    ("thin_lto_assertions", True, "table", "thin", {}),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command(args, *, cwd, environment, log, timeout=180):
    process = subprocess.Popen(args, cwd=cwd, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    log.write_text("COMMAND " + json.dumps(args) + "\nSTDOUT\n" + stdout +
                   "\nSTDERR\n" + stderr + "\nEXIT " + str(process.returncode) + "\n")
    if timed_out or process.returncode:
        raise AssertionError(f"command exited{process.returncode}; timeout={timed_out}; see {log}")
    return stdout



def manifest(*, inline, assertions, lto):
    profile = (f'opt-level = 3, debug = 2, debug-assertions = {str(assertions).lower()}, '
               f'lto = "{lto}", codegen-units = 1, split-debuginfo = "off", panic = "abort"')
    fields = ('[profile]\nrelease = { ' + profile + ' }\n' if inline else
              '[profile.release]\n' + profile.replace(', ', '\n') + '\n')
    return ('[package]\nname = "stt-override-effect-probe"\nversion = "0.0.0"\n'
            'edition = "2021"\n[workspace]\n' + fields)


def scan(scanner, artifact: Path, log: Path):
    out, err = io.StringIO(), io.StringIO()
    rejected = False
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            scanner.run_scan(artifact.parent,
                ((artifact.name, scanner.MIN_ARTEFACT_BYTES, "real native STT selector probe"),),
                scanner.SIGNATURES)
        except scanner.ScanError as error:
            rejected = True
            print(str(error), file=sys.stderr)
    log.write_text("STDOUT\n" + out.getvalue() + "\nSTDERR\n" + err.getvalue())
    return rejected, scanner.scan_file(artifact, scanner.SIGNATURES)



def module_tests(source, toolchain, output, environment):
    """Compile every test in the owning std-only module; scan the real operator src tree."""
    wrapper = output / "selector-module-tests.rs"
    wrapper.write_text(
        '#[allow(dead_code)]\n#[path = ' + json.dumps(str(source), ensure_ascii=False) + ']\n'
        'mod stt_model_source;\n'
        "fn env_locked() -> std::sync::MutexGuard<'static, ()> {\n"
        '    static ENV: std::sync::Mutex<()> = std::sync::Mutex::new(());\n'
        '    ENV.lock().unwrap_or_else(|poisoned| poisoned.into_inner())\n}\n')
    test_env = dict(environment, CARGO_MANIFEST_DIR=str(source.parent.parent))
    for name, level, assertions in (("debug", "0", "yes"), ("release", "3", "no")):
        binary = output / ("module-tests-" + name)
        command(["rustc", "+" + toolchain, "--edition=2021", "--test", str(wrapper),
                 "--crate-name", "selector_module_tests", "-C", "opt-level=" + level,
                 "-C", "debug-assertions=" + assertions, "-D", "warnings", "-o", str(binary)],
                cwd=output, environment=test_env, log=output / ("module-" + name + "-compile.log"))
        command([str(binary), "--test-threads=1"], cwd=output, environment=test_env,
                log=output / ("module-" + name + "-tests.log"))


def verify(root: Path, output: Path, operators):
    if sys.platform not in {"darwin", "linux"}:
        raise AssertionError("native effect probe supports macOS/Linux; no Windows installer claim")
    source = root / "implementation/desktop/crates/selahcue-operator/src/stt_model_source.rs"
    scanner_path = root / "scripts/installer_secret_scan.py"
    pinned = re.search(r'(?m)^channel\s*=\s*"(\d+\.\d+\.\d+)"',
                       (root / "rust-toolchain.toml").read_text())
    if pinned is None:
        raise AssertionError("cannot identify the repository's exact Rust toolchain")
    toolchain = pinned.group(1)
    spec = importlib.util.spec_from_file_location("installer_scanner_effect_probe", scanner_path)
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    # Isolate every source of ambient Cargo flags/configuration, without reading credentials.
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("CARGO_") and key not in {
                       "RUSTFLAGS", "RUSTC", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER",
                       "RUSTC_BOOTSTRAP", "SELAHCUE_STT_MODEL", "SELAHCUE_STT_MODEL_SHA256"}}
    environment.update(CARGO_HOME=str(output / "cargo-home"), CARGO_NET_OFFLINE="true",
                       CARGO_INCREMENTAL="0")
    strip = shutil.which("strip")
    if strip is None:
        raise AssertionError("native strip tool required for optimizer-retention proof")
    report = {"source": str(source), "source_sha256": sha256(source),
              "scanner_sha256": sha256(scanner_path), "toolchain": toolchain,
              "platform": platform.platform(), "cases": [], "status": "FAIL"}
    try:
        report["operator_cases"] = []
        for artifact, unsafe in operators:
            if artifact.stat().st_size < scanner.MIN_ARTEFACT_BYTES:
                raise AssertionError("real operator artifact is below unchanged shipping floor")
            expected_magic = b"\xcf\xfa\xed\xfe" if sys.platform == "darwin" else b"\x7fELF"
            with artifact.open("rb") as stream:
                magic = stream.read(4)
            if magic != expected_magic:
                raise AssertionError("operator proof requires an actual native executable")
            rejected, hits = scan(scanner, artifact, output / ("operator-unsafe-scan.log" if unsafe else "operator-normal-scan.log"))
            report["operator_cases"].append({"path": str(artifact), "bytes": artifact.stat().st_size,
                "sha256": sha256(artifact), "scanner_rejected": rejected, "hits": hits})
            if rejected != unsafe or any(hit[0] == EXPECTED_MARKER for hit in hits) != unsafe:
                raise AssertionError("full native operator gate did not track the STT override capability")
        report["rustc"] = command(["rustc", "+" + toolchain, "-vV"], cwd=output,
            environment=environment, log=output / "rustc.log")
        module_tests(source, toolchain, output, environment)
        report["owning_module_debug_release_tests"] = "PASS"
        for name, unsafe, style, lto, overrides in CASES:
            work = output / name
            (work / "src").mkdir(parents=True)
            # Only the manifest-profile cases enable assertions in TOML. The other cases
            # must prove their environment/legacy-config input changes actual emitted code.
            assertions = unsafe and name in {"profile_assertions", "inline_profile", "thin_lto_assertions"}
            (work / "Cargo.toml").write_text(manifest(inline=style == "inline", assertions=assertions, lto=lto))
            (work / "src/main.rs").write_text(
                '#[allow(dead_code)]\n#[path = ' + json.dumps(str(source), ensure_ascii=False) + ']\nmod stt_model_source;\n'
                'fn main() {\n    match stt_model_source::model_source_from_env() {\n'
                '        stt_model_source::ModelSource::Pinned => println!("pinned"),\n'
                '        stt_model_source::ModelSource::DeveloperOverride { .. } => println!("override"),\n'
                '    }\n}\n')
            if style == "legacy":
                (work / ".cargo").mkdir()
                (work / ".cargo/config").write_text('[build]\nrustflags = ["-C", "debug-assertions"]\n')
            build_env = dict(environment, **overrides)
            build_env["CARGO_TARGET_DIR"] = str(work / "target")
            command(["cargo", "+" + toolchain, "generate-lockfile", "--offline"], cwd=work,
                    environment=build_env, log=work / "lock.log")
            command(["cargo", "+" + toolchain, "build", "--release", "--offline", "--locked"],
                    cwd=work, environment=build_env, log=work / "build.log")
            artifact = work / "target/release" / BINARY_NAME
            runtime_env = dict(environment, SELAHCUE_STT_MODEL="synthetic-effect-probe-model.bin",
                               SELAHCUE_STT_MODEL_SHA256="0" * 64)
            actual = command([str(artifact)], cwd=work, environment=runtime_env,
                             log=work / "runtime.log").strip()
            if actual != ("override" if unsafe else "pinned"):
                raise AssertionError(f"{name}: real production selector effect was {actual!r}")
            runtime_log = (work / "runtime.log").read_text()
            if (EXPECTED_MARKER in runtime_log) != unsafe:
                raise AssertionError(f"{name}: real stderr notice did not track the override path")
            if "synthetic-effect-probe-model.bin" in runtime_log or "0" * 64 in runtime_log:
                raise AssertionError(f"{name}: notice disclosed a supplied path or hash")
            full_gate_rejected, hits = scan(scanner, artifact, work / "scan.log")
            below_floor = artifact.stat().st_size < scanner.MIN_ARTEFACT_BYTES
            if below_floor and not full_gate_rejected:
                raise AssertionError("shipping scanner floor was weakened for small probe")
            rejected = bool(hits)  # supplemental matcher verdict, never floor acceptance
            row = {"name": name, "unsafe_effect": unsafe, "runtime": actual,
                   "lto": lto, "bytes": artifact.stat().st_size, "sha256": sha256(artifact),
                   "matcher_rejected": rejected, "full_gate_rejected": full_gate_rejected,
                   "below_shipping_floor": below_floor, "hits": hits}
            report["cases"].append(row)
            if unsafe and not any(hit[0] == EXPECTED_MARKER for hit in hits):
                raise AssertionError(f"{name}: actual override is reachable but scanner missed its compiled marker")
            if rejected != unsafe or (not unsafe and hits):
                raise AssertionError(f"{name}: scanner did not match real unsafe capability")
            stripped = work / "stripped-probe"
            args = [strip, "-S", "-o", str(stripped), str(artifact)] if sys.platform == "darwin" else [strip, "--strip-debug", "-o", str(stripped), str(artifact)]
            command(args, cwd=work, environment=environment, log=work / "strip.log")
            stripped_hits = scanner.scan_file(stripped, scanner.SIGNATURES)
            row.update(stripped_bytes=stripped.stat().st_size, stripped_sha256=sha256(stripped),
                       stripped_hits=stripped_hits)
            if any(hit[0] == EXPECTED_MARKER for hit in stripped_hits) != unsafe:
                raise AssertionError(f"{name}: marker did not track actual override after debug stripping")
            if not unsafe and stripped_hits:
                raise AssertionError(f"{name}: normal stripped release has an unsafe signature")
            print(f"PASS {name}: runtime={actual}, matcher={'RED' if rejected else 'GREEN'}, {lto}LTO/stripped", flush=True)
        report["status"] = "PASS"
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--normal-operator", type=Path, help="real linked normal-release operator, uncompressed")
    parser.add_argument("--unsafe-operator", type=Path, help="real linked assertions-on release operator, uncompressed")
    parser.add_argument("--supplemental-only", action="store_true", help="small-probe matcher proof ONLY; cannot satisfy full operator gate")
    parser.add_argument("--output-dir", type=Path, help="new directory for compiler/artifact/log evidence")
    args = parser.parse_args()
    if args.supplemental_only:
        if args.normal_operator or args.unsafe_operator:
            parser.error("supplemental-only must not be combined with full operator inputs")
        operators = []
    else:
        if not args.normal_operator or not args.unsafe_operator:
            parser.error("supply both real operator artifacts, or explicitly request supplemental-only evidence")
        operators = [(args.normal_operator.resolve(), False), (args.unsafe_operator.resolve(), True)]
    try:
        if args.output_dir is not None:
            args.output_dir.mkdir(parents=True, exist_ok=False)
            verify(args.root.resolve(), args.output_dir.resolve(), operators)
        else:
            with tempfile.TemporaryDirectory(prefix="selahcue-stt-effect-") as directory:
                verify(args.root.resolve(), Path(directory), operators)
    except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
        print(f"STT artifact effect proof FAILED: {error}", file=sys.stderr)
        return 1
    print("SUPPLEMENTAL matcher/module proof PASS; full operator acceptance NOT executed" if args.supplemental_only else
          "STT artifact effect proof PASS: full native operator scanner plus source-exact optimized/stripped module; not a Windows installer build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
