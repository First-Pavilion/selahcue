#!/usr/bin/env python3
"""Offline controls for the joint gate using synthetic Cargo, executable and JUnit data."""

import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import g1_operator_artifact as gate

SOURCE = "1" * 40
TEST_NAME = "account::tests::controller::django_g1_real_api"
JOINT_CLASS = "tests.test_native_account_controller_integration"
JOINT_TEST = "test_native_account_controller_against_local_platform_api"


class GateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.cargo = self.root / "cargo.jsonl"
        self.artifact = self.root / "artifact"
        self.executable = self.root / "build-test"
        self.executable.write_bytes(b"synthetic executable")
        self.executable.chmod(0o755)
        self.record = {
            "reason": "compiler-artifact",
            "target": {"kind": ["bin"], "name": "selahcue-operator"},
            "profile": {"test": True},
            "features": ["default", "native-account"],
            "executable": str(self.executable),
        }
        self.nodeids = self.root / "nodeids.txt"
        self.nodeids.write_text(
            "".join(f"tests/test_native_account_controller_integration.py::{JOINT_TEST}[{case}]\n"
                    for case in ("expired", "live"))
            + "\n2 tests collected in 0.02s\n",
            encoding="utf-8",
        )
        self.junit = self.root / "api-junit.xml"
        self.evidence = self.root / "g1-junit.xml"

    def write_cargo(self, *records):
        self.cargo.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    def stage(self):
        self.write_cargo({**self.record, "profile": {"test": False}}, self.record)
        with patch.object(gate, "run_command", side_effect=self.fake_tools):
            gate.stage(self.cargo, SOURCE, self.artifact)
        self.assertEqual(self.executable.read_bytes(), b"synthetic executable")

    def fake_tools(self, args, **kwargs):
        if args[0] == "strip":
            self.assertEqual(args[:3], ["strip", "--strip-debug", "--"])
            copied = Path(args[3])
            self.assertEqual(copied, self.artifact / "operator-test")
            self.assertEqual(copied.read_bytes(), self.executable.read_bytes())
            copied.write_bytes(b"stripped test executable")
            return ""
        executable = str(self.artifact / "operator-test")
        if args == ["ldd", executable]:
            return "libc.so.6 => /lib/libc.so.6 (0x01)\n"
        self.assertEqual(args, [executable, "--list", "--ignored"])
        return f"{TEST_NAME}: test\n\n1 test, 0 benchmarks\n"

    def test_stages_the_unique_default_feature_test_copy_and_verifies_it(self):
        self.stage()
        binary = self.artifact / "operator-test"
        self.assertEqual(binary.read_bytes(), b"stripped test executable")
        manifest = json.loads((self.artifact / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest, {
            "source_sha": SOURCE, "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "test_name": TEST_NAME, "default_features": True,
        })
        binary.chmod(0o644)  # actions/download-artifact does not retain the mode.
        with patch.object(gate, "run_command", side_effect=self.fake_tools):
            self.assertEqual(gate.verify(self.artifact, SOURCE), binary)
        self.assertTrue(binary.stat().st_mode & 0o100)

    def test_absent_and_ambiguous_operator_artifacts_refuse_staging(self):
        for records in (
            [{**self.record, "profile": {"test": False}}],
            [{**self.record, "features": ["native-account"]}],
            [self.record, self.record],
        ):
            with self.subTest(records=records):
                self.write_cargo(*records)
                with self.assertRaisesRegex(gate.GateError, "exactly one"):
                    gate.stage(self.cargo, SOURCE, self.artifact)
                self.assertFalse(self.artifact.exists())

    def test_symlink_executable_refuses_staging(self):
        alias = self.root / "alias"
        alias.symlink_to(self.executable)
        self.write_cargo({**self.record, "executable": str(alias)})
        with self.assertRaisesRegex(gate.GateError, "symlink"):
            gate.stage(self.cargo, SOURCE, self.artifact)

    def test_source_and_hash_mismatches_refuse_execution(self):
        self.stage()
        with self.assertRaisesRegex(gate.GateError, "source SHA"):
            gate.verify(self.artifact, "2" * 40)
        (self.artifact / "operator-test").write_bytes(b"tampered")
        with self.assertRaisesRegex(gate.GateError, "SHA-256"):
            gate.verify(self.artifact, SOURCE)

    def test_unlinked_libraries_and_missing_exact_ignored_test_both_fail(self):
        self.stage()
        for outputs, error in [
            (["libg1.so => not found"], "missing shared libraries"),
            (["libc.so.6 => /lib/libc.so.6", f"other::{TEST_NAME}: test"], "exact ignored test"),
        ]:
            with self.subTest(error=error), patch.object(gate, "run_command", side_effect=outputs):
                with self.assertRaisesRegex(gate.GateError, error):
                    gate.verify(self.artifact, SOURCE)

    def test_artifact_over_limit_reports_the_size(self):
        self.write_cargo(self.record)
        with patch.object(gate, "run_command", side_effect=self.fake_tools), patch.object(gate, "MAX_ARTIFACT", 8):
            with self.assertRaisesRegex(gate.GateError, "24 bytes"):
                gate.stage(self.cargo, SOURCE, self.artifact)

    def write_junit(self, cases):
        suite = ET.Element("testsuite")
        for case, status in cases:
            element = ET.SubElement(suite, "testcase", classname=JOINT_CLASS, name=f"{JOINT_TEST}[{case}]")
            if status:
                ET.SubElement(element, status).text = "synthetic sensitive diagnostic"
        ET.ElementTree(suite).write(self.junit, encoding="utf-8")

    def test_requires_each_collected_joint_case_and_emits_small_junit(self):
        self.write_junit([("expired", ""), ("live", "")])
        gate.verify_results(self.junit, self.nodeids, self.evidence)
        evidence = ET.parse(self.evidence)
        self.assertEqual(len(evidence.findall(".//testcase")), 2)

    def test_zero_skipped_missing_failed_and_duplicate_joint_results_fail(self):
        for cases in (
            [], [("expired", "")], [("expired", ""), ("live", "skipped")],
            [("expired", ""), ("live", "error")], [("expired", ""), ("live", "failure")],
            [("expired", ""), ("expired", ""), ("live", "")],
        ):
            with self.subTest(cases=cases):
                self.write_junit(cases)
                with self.assertRaises(gate.GateError):
                    gate.verify_results(self.junit, self.nodeids, self.evidence)
                self.assertNotIn("synthetic sensitive diagnostic", self.evidence.read_text(encoding="utf-8"))

    def test_ignores_results_with_the_wrong_class_and_requires_nonempty_collection(self):
        self.write_junit([("expired", ""), ("live", "")])
        self.junit.write_text(self.junit.read_text(encoding="utf-8").replace(JOINT_CLASS, "other.module"),
                              encoding="utf-8")
        with self.assertRaisesRegex(gate.GateError, "missing"):
            gate.verify_results(self.junit, self.nodeids)
        self.nodeids.write_text("no tests collected\n", encoding="utf-8")
        with self.assertRaisesRegex(gate.GateError, "no joint"):
            gate.verify_results(self.junit, self.nodeids)


if __name__ == "__main__":
    unittest.main()
