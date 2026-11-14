#!/usr/bin/env python3
"""Controls for the Windows and Linux installer Whisper receipt."""
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import hashlib
import unittest

from whisper_cpu_policy import REQUIRED_SOURCES, PolicyError, operator_environment, require_fresh_target, verify


class PolicyTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.target = Path(scratch.name).resolve() / "target"
        self.out = self.target / "release/build/whisper-rs-sys-abc/out"
        self.build = self.out / "build"
        self.sources = self.out / "whisper.cpp"

    def configure(self, platform):
        self.build.mkdir(parents=True)
        self.sources.mkdir()
        generator = "Ninja" if platform == "windows" else "Unix Makefiles"
        overrides = (
            "GGML_NATIVE GGML_SSE42 GGML_AVX GGML_AVX2 GGML_BMI2 GGML_FMA GGML_F16C "
            "GGML_AVX_VNNI GGML_AVX512 GGML_AVX512_VBMI GGML_AVX512_VNNI GGML_AVX512_BF16 "
            "GGML_AMX_TILE GGML_AMX_INT8 GGML_AMX_BF16 GGML_CPU_ALL_VARIANTS GGML_BACKEND_DL GGML_CCACHE"
        ).split()
        self.cache = self.build / "CMakeCache.txt"
        self.cache.write_text(
            f"CMAKE_HOME_DIRECTORY:INTERNAL={self.sources.as_posix()}\n"
            f"CMAKE_GENERATOR:INTERNAL={generator}\n"
            "CMAKE_BUILD_TYPE:STRING=Release\nCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON\n"
            "BUILD_SHARED_LIBS:BOOL=OFF\nGGML_CPU:BOOL=ON\n"
            + "".join(f"{key}:BOOL=OFF\n" for key in overrides)
        )
        self.commands = []
        for name in sorted(REQUIRED_SOURCES):
            path = self.sources / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            compiler = '"C:\\Program Files\\MSVC\\bin\\Hostx64\\x64\\cl.exe" /nologo /O2' if platform == "windows" else "/usr/bin/c++ -O3 -march=x86-64"
            self.commands.append({"directory": str(self.build), "file": str(path), "command": f'{compiler} -c "{path}"'})
        self.write_commands()
        for name in ("whisper", "ggml", "ggml-base", "ggml-cpu"):
            archive = f"{name}.lib" if platform == "windows" else f"lib{name}.a"
            folder = self.build / ("src" if name == "whisper" else "ggml/src")
            folder.mkdir(parents=True, exist_ok=True)
            (folder / archive).write_bytes(b"!<arch>\n" + bytes(64))

    def write_commands(self):
        (self.build / "compile_commands.json").write_text(json.dumps(self.commands))

    def test_overrides_cannot_bypass_operator_policy(self):
        incoming = {"PATH": "test", "GGML_NATIVE": "ON", "ggml_avx2": "ON",
                    "WHISPER_COREML": "ON", "CMAKE_TOOLCHAIN_FILE": "private",
                    "CFLAGS_x86_64_unknown_linux_gnu": "-march=native",
                    "TARGET_CXXFLAGS": "-march=native", "_CL_": "/arch:AVX2",
                    "CARGO_TARGET_DIR": "elsewhere"}
        for platform in ("linux", "windows"):
            env = operator_environment(incoming, platform, self.target)
            self.assertEqual(env["GGML_NATIVE"], "OFF")
            self.assertEqual(env["GGML_AVX2"], "OFF")
            self.assertEqual(env["PATH"], "test")
            self.assertEqual(env["CARGO_TARGET_DIR"], str(self.target))
            for key in set(incoming) - {"PATH", "GGML_NATIVE", "CARGO_TARGET_DIR"}:
                self.assertNotIn(key, env)

    def test_refuses_a_reused_operator_target(self):
        require_fresh_target(self.target)
        self.target.mkdir()
        require_fresh_target(self.target)
        (self.target / "old").touch()
        with self.assertRaisesRegex(PolicyError, "empty"):
            require_fresh_target(self.target)

    def test_linux_receipt_rejects_effective_host_or_extension_flags(self):
        self.configure("linux")
        self.assertEqual(verify(self.target, "linux")["compile_commands"], 24)
        baseline = self.commands[0]["command"]
        for flag in ("-march=native", "-march=x86-64-v2", "-mtune=native",
                     "-mavx2", "-D__AVX2__", "-D GGML_F16C=1", "@opaque.rsp"):
            with self.subTest(flag=flag):
                self.commands[0]["command"] = f"{baseline} {flag}"
                self.write_commands()
                with self.assertRaisesRegex(PolicyError, "compiler option"):
                    verify(self.target, "linux")

    def test_windows_receipt_checks_msvc_commands_across_all_sources(self):
        self.configure("windows")
        result = verify(self.target, "windows")
        self.assertEqual(result["compiler"], "MSVC")
        self.assertNotIn("Program Files", json.dumps(result))
        baseline = self.commands[-1]["command"]
        for flag in ("/arch:AVX2", "-arch:AVX512", "/favor:ATOM", "/D__BMI2__",
                     "/D GGML_AVX512_VBMI=1", "@opaque.rsp", "/clang:-mavx2"):
            with self.subTest(flag=flag):
                self.commands[-1]["command"] = f"{baseline} {flag}"
                self.write_commands()
                with self.assertRaisesRegex(PolicyError, "compiler option"):
                    verify(self.target, "windows")

    def test_windows_receipt_cli_binds_one_installer_and_blocks_ambiguous_artifacts(self):
        self.configure("windows")
        metadata = self.target.parent / "release-metadata.json"
        metadata.write_text(json.dumps({"source_sha": "test-source"}))
        installers = self.target / "release/bundle/nsis"
        installers.mkdir(parents=True)
        package = installers / "fixture-setup.exe"
        data = b"test installer bytes"
        package.write_bytes(data)
        helper = Path(__file__).with_name("whisper_cpu_policy.py")
        command = [sys.executable, str(helper), "verify-windows", str(self.target), "--metadata", str(metadata)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = json.loads(metadata.read_text())
        self.assertEqual(outcome["source_sha"], "test-source")
        self.assertEqual(outcome["installer"], package.name)
        self.assertEqual(outcome["whisper_cpu_policy"]["installer_sha256"], hashlib.sha256(data).hexdigest())
        (installers / "another-setup.exe").write_bytes(b"other")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one fresh NSIS installer", result.stderr)

    def test_requires_complete_unambiguous_build_evidence(self):
        self.configure("linux")
        original = self.cache.read_text()
        for invalid in (original.replace("GGML_AVX2:BOOL=OFF", "GGML_AVX2:BOOL=ON"),
                        original.replace("GGML_AVX2:BOOL=OFF\n", ""),
                        original + "GGML_AVX2:BOOL=OFF\n"):
            self.cache.write_text(invalid)
            with self.assertRaises(PolicyError):
                verify(self.target, "linux")
        self.cache.write_text(original)
        extra = self.cache.with_name("nested") / self.cache.name
        extra.parent.mkdir()
        extra.write_text(original)
        with self.assertRaises(PolicyError):
            verify(self.target, "linux")
        extra.unlink()
        command = self.commands.pop()
        self.write_commands()
        with self.assertRaises(PolicyError):
            verify(self.target, "linux")
        self.commands.append(command)
        self.write_commands()
        (self.build / "ggml/src/libggml-cpu.a").unlink()
        with self.assertRaises(PolicyError):
            verify(self.target, "linux")


if __name__ == "__main__":
    unittest.main(verbosity=2)
