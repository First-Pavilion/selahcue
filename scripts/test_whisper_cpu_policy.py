#!/usr/bin/env python3
"""Controls for the Windows and Linux installer Whisper receipt."""
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import hashlib
import os
import struct
import unittest

from whisper_cpu_policy import REQUIRED_SOURCES, PolicyError, operator_environment, require_fresh_target, verify


def archive_member(name, data):
    header = f"{name:<16}{0:<12}{0:<6}{0:<6}{644:<8}{len(data):<10}`\n".encode("ascii")
    return header + data + (b"\n" if len(data) % 2 else b"")


def object_archive(platform):
    if platform == "windows":
        # COFF x64, one .text section with a single RET instruction.
        header = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 0, 0)
        text = struct.pack("<8sIIIIIIHHI", b".text", 0, 0, 1, 60, 0, 0, 0, 0, 0x60500020)
        return b"!<arch>\n" + archive_member("/", bytes(4)) + archive_member("fixture.obj/", header + text + b"\xc3")

    # ELF64 x64 relocatable, with a null, .text and section-name string table entry.
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HHIQQQIHHHHHH", header, 16, 1, 62, 1, 0, 0, 88, 0, 64, 0, 0, 64, 3, 2)
    text = struct.pack("<IIQQQQIIQQ", 1, 1, 6, 0, 64, 1, 0, 0, 1, 0)
    names = struct.pack("<IIQQQQIIQQ", 7, 3, 0, 0, 65, 17, 0, 0, 1, 0)
    # Place the section table after the string table with 8-byte alignment.
    content = b"\xc3\0.text\0.shstrtab\0".ljust(24, b"\0")
    return b"!<arch>\n" + archive_member("fixture.o/", header + content + bytes(64) + text + names)


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
            (folder / archive).write_bytes(object_archive(platform))

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
                     "/D GGML_AVX512_VBMI=1", "@opaque.rsp", "/clang:-mavx2", "-mavx2", "-md"):
            with self.subTest(flag=flag):
                self.commands[-1]["command"] = f"{baseline} {flag}"
                self.write_commands()
                with self.assertRaisesRegex(PolicyError, "compiler option"):
                    verify(self.target, "windows")

    def test_windows_receipt_accepts_hyphenated_msvc_crt_switches(self):
        self.configure("windows")
        for row, runtime in zip(self.commands, ("-MD", "-MT", "-MDd", "-MTd", "/MD", "/MT")):
            row["command"] = row["command"].replace(" /nologo /O2", f" /nologo {runtime} /O2")
        self.write_commands()
        self.assertEqual(verify(self.target, "windows")["compile_commands"], 24)

    def test_receipt_rejects_malformed_archive_and_mere_signature(self):
        self.configure("linux")
        archive = self.build / "ggml/src/libggml-cpu.a"
        elf = object_archive("linux")
        for invalid in (b"!<arch>\nX", b"!<arch>\n" + bytes(64),
                        b"!<arch>\n" + archive_member("/", bytes(4)), elf[:-1],
                        object_archive("windows")):
            with self.subTest(length=len(invalid)):
                archive.write_bytes(invalid)
                with self.assertRaisesRegex(PolicyError, "archive evidence"):
                    verify(self.target, "linux")

    def test_windows_prepare_cli_writes_policy_for_the_standalone_build(self):
        env_file = self.target.parent / "github-env"
        helper = Path(__file__).with_name("whisper_cpu_policy.py")
        command = [sys.executable, str(helper), "prepare-windows", str(self.target)]
        env = {"PATH": os.environ["PATH"], "GITHUB_ENV": str(env_file), "GGML_NATIVE": "ON"}
        if os.name == "nt":
            env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = dict(line.split("=", 1) for line in env_file.read_text().splitlines())
        self.assertEqual(settings["GGML_NATIVE"], "OFF")
        self.assertEqual(settings["CMAKE_GENERATOR"], "Ninja")
        self.assertEqual(Path(settings["CARGO_TARGET_DIR"]), self.target)
        for name in ("GGML_CPU_ARM_ARCH", "CMAKE_TOOLCHAIN_FILE", "_CL_"):
            with self.subTest(name=name):
                env_file.unlink(missing_ok=True)
                result = subprocess.run(command, env={**env, name: "unexpected"}, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(env_file.exists())

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
