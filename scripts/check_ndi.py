#!/usr/bin/env python3
"""Link-free NDI sidecar check/lint using committed headers; never build/package.

The empty library is only a grafton-ndi build-script selection placeholder, not
an SDK/runtime. It lives in a private temporary directory and is passed only to
fixed cargo check/clippy commands. No caller environment or vendored SDK changes.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("implementation/desktop/crates/selahcue-desktop/src/video_sink.rs")
MARKER = "NDI_GATE_TYPE_MUTATION"
MUTANT = b'\n#[cfg(feature = "ndi")]\nfn ndi_check_gate_mutation() { let _: u8 = "NDI_GATE_TYPE_MUTATION"; }\n'


def library_path(system: str, machine: str) -> Path:
    if system == "Linux" and machine in {"x86_64", "AMD64"}:
        return Path("lib/x86_64-linux-gnu/libndi.so")
    if system == "Darwin" and machine in {"arm64", "aarch64", "x86_64"}:
        return Path("lib/macOS/libndi.dylib")
    raise ValueError(f"Unsupported check-only host: {system}/{machine}")


@contextmanager
def check_environment(root: Path, system: str, machine: str):
    relative = library_path(system, machine)
    headers = root / "implementation/desktop/vendor/ndi/windows/include"
    if not (headers / "Processing.NDI.Lib.h").is_file():
        raise ValueError("Committed NDI headers are missing")
    with tempfile.TemporaryDirectory(prefix="selahcue-ndi-check-only-") as directory:
        sdk = Path(directory)
        shutil.copytree(headers, sdk / "include")
        library = sdk / relative
        library.parent.mkdir(parents=True)
        library.write_bytes(b"")
        (sdk / "CHECK-ONLY.txt").write_text("Empty selection placeholder. Never link, package or upload.\n")
        env = os.environ.copy()
        env["NDI_SDK_DIR"] = str(sdk)
        yield env


def command(tool: str) -> list[str]:
    if tool not in {"check", "clippy"}:
        raise ValueError("Only link-free check and clippy are permitted")
    argv = ["cargo", tool, "--locked", "-p", "selahcue-desktop", "--features", "ndi", "--all-targets"]
    if tool == "clippy":
        argv += ["--", "-D", "warnings"]
    return argv


def execute(root: Path, *, mutation_proof: bool, runner=subprocess.run) -> None:
    cwd = root / "implementation/desktop"
    with check_environment(root, platform.system(), platform.machine()) as env:
        for tool in ("check", "clippy"):
            argv = command(tool)
            print("NDI check-only: " + " ".join(argv), flush=True)
            runner(argv, cwd=cwd, env=env, check=True)
        if not mutation_proof:
            return
        source = root / SOURCE
        original = source.read_bytes()
        if MARKER.encode() in original:
            raise ValueError("Mutation marker already present; refusing to overwrite source")
        try:
            source.write_bytes(original + MUTANT)
            result = runner(command("check"), cwd=cwd, env=env, check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output = result.stdout or ""
            if result.returncode == 0 or "error[E0308]" not in output or MARKER not in output:
                print(output, file=sys.stderr)
                raise ValueError("NDI mutation did not produce its expected gated type error")
            print(output, end="", flush=True)
            print("NDI mutation proof: expected E0308 from gated source; restoring original", flush=True)
        finally:
            source.write_bytes(original)
        # Ensure restoration is not just a filesystem claim.
        runner(command("check"), cwd=cwd, env=env, check=True)


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ndi-helper-controls-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        headers = self.root / "implementation/desktop/vendor/ndi/windows/include"
        headers.mkdir(parents=True)
        (headers / "Processing.NDI.Lib.h").write_bytes(b"real-header-control")
        source = self.root / SOURCE
        source.parent.mkdir(parents=True)
        source.write_bytes(b"// original source\n")

    def test_private_stage_and_cleanup(self):
        for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64")):
            with check_environment(self.root, system, machine) as env:
                sdk = Path(env["NDI_SDK_DIR"])
                self.assertEqual(sdk.stat().st_mode & 0o777, 0o700)
                self.assertEqual((sdk / library_path(system, machine)).read_bytes(), b"")
                self.assertEqual((sdk / "include/Processing.NDI.Lib.h").read_bytes(), b"real-header-control")
            self.assertFalse(sdk.exists())

    def test_failure_cleans_stage(self):
        with self.assertRaises(RuntimeError):
            with check_environment(self.root, "Linux", "x86_64") as env:
                sdk = Path(env["NDI_SDK_DIR"])
                raise RuntimeError("subprocess failed")
        self.assertFalse(sdk.exists())

    def test_no_build_command_or_unsupported_host(self):
        for tool in ("build", "test", "run", "package"):
            with self.subTest(tool=tool), self.assertRaises(ValueError):
                command(tool)
        with self.assertRaises(ValueError):
            library_path("Windows", "AMD64")

    def test_mutation_failure_restores_source(self):
        original = (self.root / SOURCE).read_bytes()
        staged = []
        def runner(argv, **kwargs):
            staged.append(Path(kwargs["env"]["NDI_SDK_DIR"]))
            if kwargs.get("check") is False:
                return subprocess.CompletedProcess(argv, 1, "unrelated toolchain failure")
            return subprocess.CompletedProcess(argv, 0)
        with self.assertRaisesRegex(ValueError, "expected gated type error"):
            execute(self.root, mutation_proof=True, runner=runner)
        self.assertEqual((self.root / SOURCE).read_bytes(), original)
        self.assertTrue(staged and all(not p.exists() for p in staged))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--mutation-proof", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        return 0 if result.wasSuccessful() else 1
    try:
        execute(ROOT, mutation_proof=args.mutation_proof)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"NDI check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
