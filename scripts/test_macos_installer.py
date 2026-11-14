#!/usr/bin/env python3
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import build_macos_installer as build


class MacOSPackagingTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name).resolve()
        self.desktop = self.scratch / "desktop"
        self.sdk = self.desktop / "vendor/ndi/macos"
        self.target_dir = self.scratch / "target"

    def test_build_environments_exclude_developer_values_and_pin_portable_operator(self):
        incoming = {
            "HOME": "/example/home", "PATH": "/untrusted/bin", "NDI_SDK_DIR": "/developer/ndi",
            "DEEPGRAM_API_KEY": "sample", "OPENAI_API_KEY": "sample",
            "SELAHCUE_PILOT_CONFIG_PATH": "/private/input",
            "CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS": "true", "TAURI_CONFIG": "{}",
            "APPLE_SIGNING_IDENTITY": "Developer ID", "APPLE_API_KEY_PATH": "/private/key",
            "RUSTFLAGS": "-C target-cpu=native", "GGML_NATIVE": "ON", "DYLD_LIBRARY_PATH": "/developer",
        }
        with patch("build_macos_installer.Path.home", return_value=Path("/release/home")):
            sidecar = build.build_environment(self.sdk)
            operator = build.build_environment(self.sdk, operator_target_dir=self.target_dir)
            with patch.dict("os.environ", incoming, clear=True):
                self.assertEqual(build.build_environment(self.sdk), sidecar)
                self.assertEqual(
                    build.build_environment(self.sdk, operator_target_dir=self.target_dir), operator
                )
        self.assertEqual(sidecar["CARGO_BUILD_JOBS"], "1")
        self.assertEqual(sidecar["MACOSX_DEPLOYMENT_TARGET"], "13.0")
        self.assertNotIn("GGML_NATIVE", sidecar)
        for name in ("NATIVE", "SSE42", "AVX", "AVX2", "BMI2", "FMA", "F16C"):
            self.assertEqual(operator[f"GGML_{name}"], "OFF")

    def receipt(self, binary: Path, *, debug=False):
        return json.dumps({
            "reason": "compiler-artifact", "target": {"name": "selahcue-output", "kind": ["bin"]},
            "profile": {"debug_assertions": debug}, "fresh": False, "executable": str(binary),
        })

    def test_cargo_artifact_requires_a_current_release_receipt_and_target_path(self):
        target = "aarch64-apple-darwin"
        path = self.target_dir / target / "release/selahcue-output"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"fixture")
        for receipt in ("", self.receipt(path, debug=True), self.receipt(path) + "\n" + self.receipt(path),
                        self.receipt(self.scratch / "old-target/selahcue-output")):
            with self.subTest(receipt=receipt), self.assertRaises(build.PackagingError):
                build.sidecar_artifact(receipt, self.target_dir, target)
        with patch("build_macos_installer.architectures", return_value={"x86_64"}):
            with self.assertRaisesRegex(build.PackagingError, "arm64"):
                build.sidecar_artifact(self.receipt(path), self.target_dir, target)
        with patch("build_macos_installer.architectures", return_value={"arm64"}):
            self.assertEqual(build.sidecar_artifact(self.receipt(path), self.target_dir, target), path)

    def test_cargo_reports_a_stale_sidecar_even_at_the_correct_path(self):
        target = "aarch64-apple-darwin"
        path = self.target_dir / target / "release/selahcue-output"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"old build")
        receipt = json.loads(self.receipt(path))
        receipt["fresh"] = True
        with patch("build_macos_installer.architectures", return_value={"arm64"}):
            with self.assertRaisesRegex(build.PackagingError, "current"):
                build.sidecar_artifact(json.dumps(receipt), self.target_dir, target)

    def whisper_output(self, target, arch, *, tuning_flag="", native="OFF"):
        out = self.target_dir / target / "release/build/whisper-rs-sys-fixture/out/build"
        cpu = out / "ggml/src/CMakeFiles/ggml-cpu.dir"
        cpu.mkdir(parents=True)
        entries = [f"CMAKE_OSX_ARCHITECTURES:STRING={arch}"]
        entries.extend(
            f"GGML_{name}:BOOL={native if name == 'NATIVE' else 'OFF'}"
            for name in ("NATIVE", "SSE42", "AVX", "AVX2", "BMI2", "FMA", "F16C")
        )
        (out / "CMakeCache.txt").write_text("\n".join(entries))
        (cpu / "flags.make").write_text(
            f"C_FLAGS = -O3 -arch {arch} {tuning_flag}\n"
            f"CXX_FLAGS = -O3 -arch {arch} {tuning_flag}\n"
        )
        return cpu

    def test_portability_check_reads_actual_cpu_flags_for_both_slices(self):
        self.whisper_output("aarch64-apple-darwin", "arm64")
        intel = self.whisper_output("x86_64-apple-darwin", "x86_64", tuning_flag="-march=native")
        with self.assertRaisesRegex(build.PackagingError, "x86_64.*-march=native"):
            build.check_whisper_flags(self.target_dir)
        shutil.rmtree(intel.parents[2])
        self.whisper_output("x86_64-apple-darwin", "x86_64")
        self.assertEqual(set(build.check_whisper_flags(self.target_dir)), {"arm64", "x86_64"})

    def test_native_whisper_cache_and_missing_slice_both_fail(self):
        arm = self.whisper_output("aarch64-apple-darwin", "arm64", native="ON")
        with self.assertRaisesRegex(build.PackagingError, "GGML_NATIVE"):
            build.check_whisper_flags(self.target_dir)
        shutil.rmtree(arm.parents[2])
        self.whisper_output("aarch64-apple-darwin", "arm64")
        with self.assertRaisesRegex(build.PackagingError, "x86_64"):
            build.check_whisper_flags(self.target_dir)

    def test_compiler_architecture_prefix_cannot_satisfy_the_slice_check(self):
        self.whisper_output("aarch64-apple-darwin", "arm64")
        intel = self.whisper_output("x86_64-apple-darwin", "x86_64")
        flags = intel / "flags.make"
        flags.write_text(flags.read_text().replace("-arch x86_64", "-arch x86_64h"))
        with self.assertRaisesRegex(build.PackagingError, "x86_64 target"):
            build.check_whisper_flags(self.target_dir)

    def test_old_dmg_cannot_be_mistaken_for_the_current_build(self):
        package = self.scratch / "old.dmg"
        package.write_bytes(b"old package")
        with self.assertRaisesRegex(build.PackagingError, "already exists"):
            build.require_new_file(package)
        build.require_new_file(self.scratch / "new.dmg")


if __name__ == "__main__":
    unittest.main()
