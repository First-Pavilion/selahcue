#!/usr/bin/env python3
"""Regression controls for candidate Ubuntu prerequisite inspection, not package QA."""
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest

from ubuntu_packaging_preflight import inspect_repo


TARGET = "x86_64-unknown-linux-gnu"


def elf(machine=62):
    data = bytearray(64)
    data[:4] = b"\x7fELF"
    data[4:7] = bytes((2, 1, 1))
    struct.pack_into("<H", data, 18, machine)
    return data


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.op = self.root / "implementation/desktop/crates/selahcue-operator"
        self.op.mkdir(parents=True)
        self.cfg = {"build": {"frontendDist": "dist"}, "bundle": {
            "targets": ["deb"], "externalBin": ["binaries/selahcue-output"],
            "resources": {}}}
        (self.op / "dist").mkdir()
        (self.op / "dist/index.html").write_text("fixture")
        self.sidecar = self.op / f"binaries/selahcue-output-{TARGET}"
        self.sidecar.parent.mkdir()
        self.sidecar.write_bytes(elf())
        self.sidecar.chmod(self.sidecar.stat().st_mode | stat.S_IXUSR)

    def run_report(self, ndi="disabled"):
        (self.op / "tauri.conf.json").write_text(json.dumps(self.cfg))
        return inspect_repo(self.root, TARGET, ndi)

    def blocked(self, report, check):
        self.assertFalse(report["input_checks_passed"])
        self.assertTrue(any(c["id"] == check and c["status"] == "blocked"
                            for c in report["checks"]), report)

    def test_valid_fixture_never_claims_release_readiness(self):
        report = self.run_report()
        self.assertTrue(report["input_checks_passed"], report)
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["matrix_status"], "candidate-not-validated")

    def test_windows_nsis_and_dll_are_rejected(self):
        self.cfg["bundle"]["targets"] = ["nsis"]
        self.cfg["bundle"]["resources"] = {"binaries/runtime.dll": "runtime.dll"}
        report = self.run_report()
        self.blocked(report, "package-format")
        self.blocked(report, "windows-resources")

    def test_absent_sidecar_rejected(self):
        self.sidecar.unlink()
        self.blocked(self.run_report(), "sidecar")

    def test_empty_compile_placeholder_rejected(self):
        self.sidecar.write_bytes(b"")
        self.blocked(self.run_report(), "sidecar")

    def test_truncated_or_windows_binary_rejected(self):
        for payload in (b"\x7fELF", b"MZ" + bytes(80)):
            with self.subTest(payload=payload[:4]):
                self.sidecar.write_bytes(payload)
                self.blocked(self.run_report(), "sidecar")

    def test_wrong_architecture_rejected(self):
        self.sidecar.write_bytes(elf(183))
        self.blocked(self.run_report(), "sidecar")

    def test_non_executable_sidecar_rejected(self):
        self.sidecar.chmod(0o644)
        self.blocked(self.run_report(), "sidecar")

    def test_external_bin_declaration_required(self):
        self.cfg["bundle"]["externalBin"] = []
        self.blocked(self.run_report(), "sidecar-declaration")

    def test_missing_frontend_rejected(self):
        (self.op / "dist/index.html").unlink()
        self.blocked(self.run_report(), "frontend")

    def test_ndi_undecided_never_silently_disables_feature(self):
        self.blocked(self.run_report("undecided"), "ndi-decision")

    def test_ndi_enabled_requires_real_sdk_and_runtime(self):
        self.blocked(self.run_report("enabled"), "ndi-sdk")

    def test_ndi_fixture_has_to_supply_both_header_and_native_library(self):
        sdk = self.root / "implementation/desktop/vendor/ndi/linux"
        header = sdk / "include/Processing.NDI.Lib.h"
        library = sdk / "lib/x86_64-linux-gnu/libndi.so"
        header.parent.mkdir(parents=True)
        library.parent.mkdir(parents=True)
        header.write_text("fixture header")
        self.blocked(self.run_report("enabled"), "ndi-sdk")
        library.write_bytes(elf())
        report = self.run_report("enabled")
        self.assertTrue(report["input_checks_passed"], report)
        self.assertFalse(report["release_ready"])

    def test_missing_or_malformed_configuration_is_actionable(self):
        for content in ("not JSON", "[]"):
            (self.op / "tauri.conf.json").write_text(content)
            report = inspect_repo(self.root, TARGET, "disabled")
            self.blocked(report, "configuration")

    def test_unreviewed_target_is_rejected(self):
        (self.op / "tauri.conf.json").write_text(json.dumps(self.cfg))
        self.blocked(inspect_repo(self.root, "aarch64-unknown-linux-gnu", "disabled"), "candidate-target")


if __name__ == "__main__":
    unittest.main()
