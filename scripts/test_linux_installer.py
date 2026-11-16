#!/usr/bin/env python3
import contextlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import struct
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from build_linux_installer import (effective_config, build_environment, build_commands,
                                   stage_sidecar, select_deb, validate_config, PackagingError,
                                   require_fresh_bundle_directory, scan_package, check_elf_closure)
from installer_secret_scan import ScanError
from test_whisper_cpu_policy import PolicyTests
from smoke_linux_install import request, main as smoke_main


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.op = self.root / "implementation/desktop/crates/selahcue-operator"
        self.op.mkdir(parents=True)
        self.base = {"bundle": {"targets": ["nsis"], "resources": {"binaries/NDI.dll": "NDI.dll"},
                                "externalBin": ["binaries/selahcue-output"]}, "build": {"frontendDist": "dist"}}
        (self.op / "tauri.conf.json").write_text(json.dumps(self.base))
        (self.op / "tauri.linux.conf.json").write_text(json.dumps({"bundle": {"targets": ["deb"], "resources": []}}))

    def test_linux_array_replaces_windows_resource_map_and_preserves_base(self):
        got = effective_config(self.root)
        self.assertEqual(got["bundle"]["resources"], [])
        self.assertEqual(got["bundle"]["targets"], ["deb"])
        self.assertEqual(json.loads((self.op / "tauri.conf.json").read_text()), self.base)
        validate_config(got)

    def test_inspection_cli_validates_effective_config_without_building(self):
        script = Path(__file__).with_name("build_linux_installer.py")
        result = subprocess.run([sys.executable, str(script), "--root", str(self.root), "--inspect-config"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["bundle"]["targets"], ["deb"])
        self.assertFalse(value["public_download_ready"])

    def run_installed_smoke(self, connected):
        app = self.root / "installed/selahcue-operator"
        app.parent.mkdir()
        app.write_bytes(b"fixture")
        (app.parent / "selahcue-output").write_bytes(b"fixture")
        def response(_base, path, body=None, method=None):
            if path == "/status":
                return {"ready": True}
            if path == "/session":
                return {"sessionId": "fixture-session"}
            if path.endswith("/execute/async"):
                return connected
            return None
        with patch("sys.argv", ["smoke", "--application", str(app)]), \
             patch.dict("os.environ", {}, clear=True), \
             patch("smoke_linux_install.subprocess.Popen") as spawn, \
             patch("smoke_linux_install.os.killpg") as kill, \
             patch("smoke_linux_install.time.sleep"), \
             patch("smoke_linux_install.request", side_effect=response) as transport, \
             contextlib.redirect_stdout(io.StringIO()):
            spawn.return_value.pid = 2_000_000_000
            spawn.return_value.poll.return_value = None
            if connected is True:
                self.assertEqual(smoke_main(), 0)
            else:
                with self.assertRaisesRegex(RuntimeError, "real audience backend"):
                    smoke_main()
            self.assertTrue(kill.called)
            self.assertTrue(any(call.kwargs.get("method") == "DELETE" for call in transport.call_args_list))

    def test_demo_false_reply_cannot_pass_even_when_webdriver_session_exists(self):
        self.run_installed_smoke(False)

    def test_actual_true_reply_finishes_and_closes_the_session(self):
        self.run_installed_smoke(True)

    def test_webdriver_error_is_not_accepted_or_echoed(self):
        reply = io.BytesIO(b'{"value":{"error":"failed","message":"sensitive response body"}}')
        with patch("urllib.request.urlopen", return_value=reply):
            with self.assertRaisesRegex(RuntimeError, "^Installed-app WebDriver command failed$"):
                request("http://127.0.0.1:4444", "/session")

    def test_empty_resource_object_is_not_a_valid_override(self):
        (self.op / "tauri.linux.conf.json").write_text('{"bundle":{"targets":["deb"],"resources":{}}}')
        with self.assertRaises(PackagingError):
            validate_config(effective_config(self.root))

    def test_commands_preserve_release_defaults_and_forbid_ndi_or_dev_features(self):
        sidecar, operator = build_commands(self.root)
        self.assertIn("--release", sidecar)
        self.assertIn("--locked", sidecar)
        self.assertNotIn("--no-default-features", sidecar + operator)
        self.assertNotIn("ndi", sidecar + operator)
        self.assertIn("stt", operator)
        self.assertNotIn("dev-keys", sidecar + operator)
        self.assertNotIn("--debug", operator)

    def test_developer_overrides_are_removed_without_printing_values(self):
        incoming = {"PATH": "/bin", "OPENAI_API_KEY": "private", "DEEPGRAM_API_KEY": "private",
                    "RUSTFLAGS": "debug-assertions=yes", "CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS": "true",
                    "CARGO_TARGET_DIR": "/stale", "TAURI_CONFIG": "override", "LD_LIBRARY_PATH": "/dev",
                    "NDI_SDK_DIR": "/sdk", "SELAHCUE_CLOUD_URL": "https://example.test"}
        self.assertEqual(build_environment(incoming), {"PATH": "/bin"})

    def test_sidecar_staging_rejects_empty_debug_and_wrong_architecture(self):
        src = self.root / "output"
        for payload in (b"", b"MZ" + bytes(80), b"\x7fELF"):
            src.write_bytes(payload)
            with self.assertRaises(PackagingError):
                stage_sidecar(src, self.op / "binaries/sidecar", debug_assertions=False)
        data = bytearray(1_000_000)
        data[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into("<H", data, 18, 62)
        src.write_bytes(data)
        with self.assertRaises(PackagingError):
            stage_sidecar(src, self.op / "binaries/sidecar", debug_assertions=True)
        dst = self.op / "binaries/sidecar"
        stage_sidecar(src, dst, debug_assertions=False)
        self.assertEqual(dst.read_bytes(), data)
        self.assertTrue(dst.stat().st_mode & stat.S_IXUSR)

    def test_wrong_elf_cpu_is_rejected_even_at_real_artifact_size(self):
        data = bytearray(1_000_000)
        data[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into("<H", data, 18, 183)
        source = self.root / "wrong-arch"
        source.write_bytes(data)
        with self.assertRaises(PackagingError):
            stage_sidecar(source, self.root / "destination", debug_assertions=False)

    def test_old_bundle_is_rejected_before_tauri_can_reuse_it(self):
        bundle = self.root / "old-bundle"
        require_fresh_bundle_directory(bundle)
        bundle.mkdir()
        require_fresh_bundle_directory(bundle)
        (bundle / "stale.deb").write_bytes(b"stale")
        with self.assertRaises(PackagingError):
            require_fresh_bundle_directory(bundle)

    def test_scanner_reads_both_uncompressed_binaries_and_deb(self):
        unpacked = self.root / "unpacked"
        binary_dir = unpacked / "usr/bin"
        binary_dir.mkdir(parents=True)
        for name in ("selahcue-operator", "selahcue-output"):
            (binary_dir / name).write_bytes(bytes(1_000_000))
        package = self.root / "fixture.deb"
        package.write_bytes(bytes(1_000_000))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            scan_package(unpacked, package, "selahcue-operator")
            (binary_dir / "selahcue-operator").write_bytes(b"OPENAI_API_KEY" + bytes(1_000_000))
            with self.assertRaises(ScanError):
                scan_package(unpacked, package, "selahcue-operator")
            (binary_dir / "selahcue-operator").write_bytes(bytes(1_000_000))
            (binary_dir / "selahcue-output").unlink()
            with self.assertRaises(ScanError):
                scan_package(unpacked, package, "selahcue-operator")

    def test_unresolved_ndi_and_development_rpaths_fail_closure(self):
        binary = self.root / "native"
        data = bytearray(1_000_000)
        data[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into("<H", data, 18, 62)
        binary.write_bytes(data)
        binary.chmod(0o755)
        cases = [("", "library.so => not found"), ("NEEDED libndi.so", ""),
                 (f"RUNPATH [{self.root}/target/release]", "")]
        for dynamic, linked in cases:
            with self.subTest(dynamic=dynamic, linked=linked):
                with patch("build_linux_installer.run", side_effect=[SimpleNamespace(stdout=dynamic), SimpleNamespace(stdout=linked)]):
                    with self.assertRaises(PackagingError):
                        check_elf_closure(binary, self.root, {})

    def test_deb_selection_requires_one_unambiguous_package(self):
        directory = self.root / "deb"
        directory.mkdir()
        with self.assertRaises(PackagingError):
            select_deb(directory)
        (directory / "a.deb").write_bytes(b"fixture")
        self.assertEqual(select_deb(directory).name, "a.deb")
        (directory / "b.deb").write_bytes(b"fixture")
        with self.assertRaises(PackagingError):
            select_deb(directory)


if __name__ == "__main__":
    unittest.main()
