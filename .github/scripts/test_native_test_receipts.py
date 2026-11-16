#!/usr/bin/env python3
"""Exercise ci.yml's actual native-test receipt parsers without building Rust.

Run manually from any directory with the existing pinned PyYAML available:
    python3 .github/scripts/test_native_test_receipts.py

The CP1252 default models the observed Windows decoder, not this host's locale.
All bytes are synthetic; the original hosted tee tempfile was not recovered.
These controls do not establish native Windows test or whole-phase execution.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / "workflows/ci.yml"
STEP_NAMES = (
    "Test (Windows plain SQLite — full data suite)",
    "Test (Windows desktop RELEASE — full output binary suite)",
    "Focused pilot expiry (release, synthetic only)",
)
CP1252_DEFAULT = """import pathlib
_original_open = pathlib.Path.open
def _cp1252_default_open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
    return _original_open(self, mode, buffering,
        'cp1252' if encoding in (None, 'locale') else encoding, errors, newline)
pathlib.Path.open = _cp1252_default_open
"""
# Valid UTF-8 Rust-style diagnostic framing: byte 0x90 is at offset 4123,
# matching the observed exception class/byte/offset, not historical tee bytes.
DIAGNOSTIC = b"x" * 4121 + "┐\nwarning: linking object as if no debug info\n".encode("utf-8")


def receipt(names, summary="test result: ok. 10 passed; 0 failed"):
    return ("\n".join("test fixture::" + name + " ... ok" for name in names)
            + "\n" + summary + "\n").encode("ascii")


class NativeTestReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = [step for job in workflow["jobs"].values() for step in job.get("steps", [])]
        cls.blocks = []
        cls.cases = []
        for name in STEP_NAMES:
            matches = [step["run"] for step in steps if step.get("name") == name]
            if len(matches) != 1:
                raise AssertionError(f"expected one workflow block: {name}")
            block = matches[0]
            cls.blocks.append((name, block))
            snippets = [shlex.split(line.strip()) for line in block.splitlines()
                        if line.strip().startswith("python3 -c ")]
            if len(snippets) != 1:
                raise AssertionError(f"expected one real receipt parser: {name}")
            _, _, code, log_argument, *required = snippets[0]
            if log_argument != "$log":
                raise AssertionError(f"unexpected receipt path argument: {log_argument}")
            if required == ["${required[@]}"]:
                arrays = {}
                for line in block.splitlines():
                    if ") required=(" in line:
                        phase, values = line.strip().split(") required=(", 1)
                        arrays[phase] = shlex.split(values.split(")", 1)[0])
                phases = [shlex.split(line)[1] for line in block.splitlines()
                          if line.strip().startswith("run_pilot_tests ")]
                if len(phases) != 5:
                    raise AssertionError("expected all five pilot phase calls")
                for phase in phases:
                    cls.cases.append((name + ": " + phase, code, arrays.get(phase, arrays["*"])))
            else:
                cls.cases.append((name, code, required))
        if len(cls.cases) != 7 or any(not names for _, _, names in cls.cases):
            raise AssertionError("expected two native receipts and all five named pilot receipts")

    def run_parser(self, code, path, names):
        # Disable interpreter UTF-8 mode so newer Python versions also expose
        # an omitted encoding as None/"locale" to the modeled Windows default.
        return subprocess.run([sys.executable, "-X", "utf8=0", "-c", CP1252_DEFAULT + code, str(path), *names],
                              capture_output=True, text=True, encoding="utf-8", timeout=10)

    def test_valid_utf8_receipts_ignore_cp1252_default(self):
        self.assertEqual(DIAGNOSTIC[4123], 0x90)
        with tempfile.TemporaryDirectory(prefix="native-receipt-") as directory:
            path = Path(directory) / "receipt.log"
            for label, code, names in self.cases:
                with self.subTest(receipt=label):
                    path.write_bytes(DIAGNOSTIC + receipt(names))
                    result = self.run_parser(code, path, names)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("10", result.stdout)
                    self.assertIn("verified", result.stdout)

    def test_ascii_receipts_and_refusal_controls(self):
        controls = 0
        with tempfile.TemporaryDirectory(prefix="native-receipt-") as directory:
            path = Path(directory) / "receipt.log"
            for label, code, names in self.cases:
                valid = receipt(names)
                path.write_bytes(valid)
                with self.subTest(receipt=label, control="ASCII success"):
                    self.assertEqual(self.run_parser(code, path, names).returncode, 0)
                negatives = [
                    ("empty", b"", "AssertionError"),
                    ("zero tests with all names", receipt(names, "test result: ok. 0 passed; 0 failed"), "AssertionError"),
                    ("failed suite with all names", receipt(names, "test result: FAILED. 9 passed; 1 failed"), "AssertionError"),
                    ("malformed UTF-8", b"\xff\n" + valid, "UnicodeDecodeError"),
                ]
                for name in names:
                    negatives.append(("missing " + name, receipt([n for n in names if n != name]), "AssertionError"))
                    negatives.append(("failed " + name, valid.replace((name + " ... ok").encode("ascii"),
                                      (name + " ... FAILED").encode("ascii")), "AssertionError"))
                for control, payload, error in negatives:
                    with self.subTest(receipt=label, control=control):
                        path.write_bytes(payload)
                        result = self.run_parser(code, path, names)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn(error, result.stderr)
                    controls += 1
                path.unlink()
                with self.subTest(receipt=label, control="missing file"):
                    result = self.run_parser(code, path, names)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("FileNotFoundError", result.stderr)
                controls += 1
        print(f"7 ASCII successes; {controls} receipt refusal controls", flush=True)

    def test_actual_shell_blocks_stop_on_failed_producer(self):
        if os.name != "posix":
            self.fail("shell fixtures require POSIX; use hosted CI for native Windows execution")
        with tempfile.TemporaryDirectory(prefix="native-receipt-shell-") as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fixture = root / "valid-looking.log"
            names = sorted({name for _, _, required in self.cases for name in required})
            fixture.write_bytes(receipt(names))
            cargo = bin_dir / "cargo"
            cargo.write_text('#!/bin/sh\ncat "$RECEIPT_FIXTURE"\nexit 7\n', encoding="utf-8")
            parser_marker = root / "parser-reached"
            python = bin_dir / "python3"
            python.write_text('#!/bin/sh\ntouch "$PARSER_MARKER"\nexit 99\n', encoding="utf-8")
            perl = bin_dir / "perl"
            perl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            for executable in (cargo, python, perl):
                executable.chmod(0o700)
            env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                   "RECEIPT_FIXTURE": str(fixture), "PARSER_MARKER": str(parser_marker),
                   "OPENSSL_SRC_PERL": str(perl), "TMPDIR": str(root)}
            for label, block in self.blocks:
                with self.subTest(step=label):
                    result = subprocess.run(["bash", "-c", block], env=env, capture_output=True,
                                            text=True, encoding="utf-8", timeout=10)
                    self.assertIn("test result: ok. 10 passed", result.stdout)
                    self.assertEqual(result.returncode, 7, result.stderr)
                    self.assertFalse(parser_marker.exists(), "parser reached after producer failure")
        print("3 actual shell blocks: producer exit 7 prevents receipt parsing", flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
