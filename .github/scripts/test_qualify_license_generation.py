"""Standalone qualification fixtures. No project imports or runtime services."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET

import qualify_license_generation as qualification


FILE = "tests/test_route.py"
SELECTOR = f"{FILE}::test_route"
EXTRA = f"{FILE}::test_extra[edge]"
ASSERTION = "assert response.status_code == 200"
MISMATCH = r"\b500 == 200\b"


class QualificationFixtures(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix="license-qualification-fixture-")
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.junit = self.root / "junit.xml"
        self.collected = self.root / "collected.json"

    def evidence(self, *cases, collected=(SELECTOR,), calls=None):
        """Cases contain selector, optional outcome, and failure message and trace."""
        suite = ET.Element("testsuite", tests=str(len(cases)))
        for kind, attr in (("failure", "failures"), ("error", "errors"), ("skipped", "skipped")):
            suite.set(attr, str(sum(case[1] == kind for case in cases)))
        for selector, outcome, *detail in cases:
            file, name = selector.split("::", 1)
            case = ET.SubElement(suite, "testcase", classname=file[:-3].replace("/", "."), name=name)
            if outcome is not None:
                element = ET.SubElement(case, outcome, message=detail[0] if detail else "")
                if len(detail) == 2:
                    element.text = detail[1]
        ET.ElementTree(suite).write(self.junit, encoding="utf-8")
        if calls is None:
            calls = [[case[0], "passed" if case[1] is None else "failed"] for case in cases]
        receipt = {"nodes": collected, "calls": calls, "deselected": 0}
        self.collected.write_text(json.dumps(receipt), encoding="utf-8")

    def verify(self, returncode=0, *, mutant=False):
        return qualification.verify_results(
            self.junit, self.collected, returncode, files=(FILE,), required=(SELECTOR,),
            failures={SELECTOR: (ASSERTION, MISMATCH)} if mutant else None,
        )

    def child(self, script, seconds=0.4):
        return qualification.run_child(
            [sys.executable, "-c", script], cwd=self.root, env=os.environ.copy(),
            deadline=time.monotonic() + seconds,
            stdout=self.root / "stdout.log", stderr=self.root / "stderr.log",
        )

    def test_exact_baseline_outcomes_pass(self):
        self.evidence((SELECTOR, None), (EXTRA, None), collected=(SELECTOR, EXTRA))
        self.verify()

    def test_exact_behavioral_failure_qualifies_a_mutant(self):
        self.evidence((SELECTOR, "failure", "assert 500 == 200", "\n    " + ASSERTION))
        self.verify(1, mutant=True)

    def test_baseline_rejects_missing_collected_case(self):
        self.evidence((SELECTOR, None), collected=(SELECTOR, EXTRA))
        with self.assertRaises(qualification.QualificationError):
            self.verify()

    def test_baseline_rejects_wrong_returncode(self):
        self.evidence((SELECTOR, None))
        with self.assertRaises(qualification.QualificationError):
            self.verify(1)

    def test_junit_cannot_replace_an_absent_call_phase(self):
        self.evidence((SELECTOR, "failure", "assert 500 == 200", ASSERTION), calls=[])
        with self.assertRaisesRegex(qualification.QualificationError, "call-phase"):
            self.verify(1, mutant=True)

    def test_baseline_rejects_a_case_hidden_in_a_nested_suite(self):
        self.evidence((SELECTOR, None))
        root = ET.parse(self.junit)
        ET.SubElement(ET.SubElement(root.getroot(), "testsuite"), "testcase", classname="tests.other", name="extra")
        root.write(self.junit, encoding="utf-8")
        with self.assertRaisesRegex(qualification.QualificationError, "nested JUnit"):
            self.verify()

    def test_rejects_malformed_or_oversized_xml(self):
        self.evidence((SELECTOR, None))
        for xml in (b"<testsuites>", b"x" * (qualification.MAX_OUTPUT + 1)):
            with self.subTest(size=len(xml)):
                self.junit.write_bytes(xml)
                with self.assertRaises(qualification.QualificationError):
                    self.verify()

    def test_rejects_skip_error_duplicate_extra_unexpected_pass_and_other_assertion(self):
        intended = (SELECTOR, "failure", "assert 500 == 200", ASSERTION)
        for cases in (
            ((SELECTOR, "skipped"),),
            ((SELECTOR, "error", "assert 500 == 200", ASSERTION),),
            (intended, intended),
            (intended, (EXTRA, None)),
            ((SELECTOR, None),),
            ((SELECTOR, "failure", "assert 500 == 200", "assert unrelated"),),
            ((SELECTOR, "failure", "assert 409 == 200", ASSERTION),),
        ):
            with self.subTest(cases=cases):
                self.evidence(*cases)
                with self.assertRaises(qualification.QualificationError):
                    self.verify(1, mutant=True)

    def test_rejects_wrong_junit_class_even_with_matching_test_name(self):
        self.evidence((SELECTOR, "failure", "assert 500 == 200", ASSERTION))
        self.junit.write_text(self.junit.read_text().replace("tests.test_route", "tests.other_route"))
        with self.assertRaisesRegex(qualification.QualificationError, "unexpected or duplicate"):
            self.verify(1, mutant=True)

    def test_restores_source_after_failing_and_timed_out_child(self):
        source = self.root / "source.py"
        original = b"generation = 1\n"
        source.write_bytes(original)
        for script, seconds in (("raise SystemExit(1)", 0.4), ("import time; time.sleep(0.6)", 0.2)):
            with self.subTest(seconds=seconds), self.assertRaises(qualification.QualificationError):
                with qualification.mutation(source, b"= 1", b"= 0", {source: original}):
                    self.assertEqual(source.read_bytes(), b"generation = 0\n")
                    status = self.child(script, seconds)
                    if status:
                        raise qualification.QualificationError("controlled child failed")
            with self.subTest(restored=seconds):
                self.assertEqual(source.read_bytes(), original)
            source.write_bytes(original)

    def test_rejects_nonunique_edit_without_changing_bytes(self):
        source = self.root / "source.py"
        original = b"generation = 1\nother = 1\n"
        source.write_bytes(original)
        with self.assertRaises(qualification.QualificationError):
            with qualification.mutation(source, b"= 1", b"= 0", {source: original}):
                pass
        self.assertEqual(source.read_bytes(), original)

    def test_normal_child_retains_separate_output(self):
        self.assertEqual(self.child("import sys; print('one'); print('two', file=sys.stderr)"), 0)
        self.assertEqual((self.root / "stdout.log").read_bytes(), b"one\n")
        self.assertEqual((self.root / "stderr.log").read_bytes(), b"two\n")

    def test_evidence_redacts_credentials_and_keeps_the_observed_assertion(self):
        device_token = b"SC-DEV-" + b"ABCD-" * 7 + b"ABCD"
        failure = b"assert 500 == 200\n"
        data = b"Authorization: Bearer " + device_token + b"\nSQL_PASSWORD=\"placeholder!\"\n" + failure
        redacted = qualification.redact_evidence(data)
        self.assertNotIn(device_token, redacted)
        self.assertNotIn(b"placeholder!", redacted)
        self.assertIn(failure, redacted)

    def test_child_stdout_overflow_is_refused_and_bounded(self):
        with self.assertRaises(qualification.QualificationError):
            self.child(f"import sys; sys.stdout.buffer.write(b'x' * {qualification.MAX_OUTPUT + 1})")
        self.assertLessEqual((self.root / "stdout.log").stat().st_size, qualification.MAX_OUTPUT)

    def test_owned_timeout_kills_a_pipe_holding_descendant(self):
        for parent_wait in (0.0, 0.7):
            with self.subTest(parent_wait=parent_wait):
                late_write = "from pathlib import Path; import time; time.sleep(0.45); Path('survived').touch()"
                script = (
                    "import subprocess, sys, time; "
                    f"subprocess.Popen([sys.executable, '-c', {late_write!r}]); "
                    f"print('started', flush=True); time.sleep({parent_wait})"
                )
                started = time.monotonic()
                with self.assertRaisesRegex(qualification.QualificationError, "deadline"):
                    self.child(script, 0.25)
                self.assertEqual((self.root / "stdout.log").read_text(), "started\n")
                self.assertLess(time.monotonic() - started, 1)
                time.sleep(0.5)
                self.assertFalse((self.root / "survived").exists())


if __name__ == "__main__":
    unittest.main()
