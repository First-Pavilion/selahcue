"""Exercise the release dev-key scanner CLI with synthetic Cargo receipts."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCANNER = Path(__file__).with_name("dev_key_scan.py").resolve()
DEV_KEY = bytes.fromhex(
    "bf 63 2a e9 43 6c 17 0b cd 58 9f 72 3e 4d 26 91 "
    "d3 21 c4 75 b7 8c e5 5b fa 14 89 06 37 e2 ac 6f"
)
CLEAN_ARTIFACT = b"synthetic artifact"
RELEASE_LIB = "libselahcue_licensing-release.rlib"
RELEASE_EXE = "selahcue-operator-release.exe"
DEBUG_LIB = "libselahcue_licensing-debug.rlib"
DEBUG_EXE = "selahcue-operator-debug.exe"


def run_python(*args, cwd=None):
    # Keep the child's text default non-UTF-8 regardless of the test runner's locale.
    return subprocess.run(
        [sys.executable, "-X", "utf8=0", *args],
        env={**os.environ, "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0"},
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        timeout=5,
    )


def cargo_artifact(name, kind, src_path, filename, executable=None):
    return {
        "reason": "compiler-artifact",
        "target": {"name": name, "kind": [kind], "src_path": src_path},
        "filenames": [filename],
        "executable": executable,
    }


def cargo_receipt(library, executable, operator_src_path="src/main.rs"):
    return [
        cargo_artifact("selahcue_licensing", "lib", "src/lib.rs", library),
        cargo_artifact("selahcue_operator", "bin", operator_src_path, executable, executable),
    ]


class DevKeyScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe = run_python(
            "-c",
            "import codecs, locale, sys; "
            "print(sys.flags.utf8_mode, codecs.lookup(locale.getencoding()).name)",
        )
        if probe.returncode != 0 or probe.stdout.strip() != "0 ascii":
            raise AssertionError(f"Expected UTF-8 mode 0 and ASCII text decoding: {probe}")

    def setUp(self):
        self.work = Path(self.enterContext(tempfile.TemporaryDirectory()))
        key_literals = ", ".join(str(byte) for byte in DEV_KEY)
        (self.work / "trust.rs").write_text(
            f"const DEV_PUBLIC_KEY: [u8; PUBLIC_KEY_BYTES] = [{key_literals}];\n",
            encoding="ascii",
        )
        for artifact in (RELEASE_LIB, RELEASE_EXE):
            (self.work / artifact).write_bytes(CLEAN_ARTIFACT)
        for artifact in (DEBUG_LIB, DEBUG_EXE):
            self.put_key_in(artifact)
        self.release_receipt = self.work / "release.json"
        self.debug_receipt = self.work / "debug.json"
        self.write_receipt(self.release_receipt, cargo_receipt(RELEASE_LIB, RELEASE_EXE))
        self.write_receipt(self.debug_receipt, cargo_receipt(DEBUG_LIB, DEBUG_EXE))

    def put_key_in(self, artifact):
        (self.work / artifact).write_bytes(b"prefix:" + DEV_KEY + b":suffix")

    def write_receipt(self, path, records):
        json_lines = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
        path.write_bytes(json_lines.encode("utf-8"))

    def scan(self):
        return run_python(
            str(SCANNER), "trust.rs", "release.json", "debug.json", "operator", cwd=self.work
        )

    def assert_scan_ok(self):
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("== dev key scan: OK ==", result.stdout)
        self.assertIn("absent from 2 operator release artifact(s)", result.stdout)

    def assert_scan_failed(self, message):
        result = self.scan()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(message, result.stderr)
        self.assertNotIn("== dev key scan: OK ==", result.stdout)
        return result

    def test_accepts_ascii_metadata(self):
        self.assert_scan_ok()

    def test_accepts_utf8_metadata_with_ascii_text_default(self):
        src_path = "src/\u0410/main.rs"
        self.write_receipt(self.release_receipt, cargo_receipt(RELEASE_LIB, RELEASE_EXE, src_path))
        self.write_receipt(self.debug_receipt, cargo_receipt(DEBUG_LIB, DEBUG_EXE, src_path))
        for receipt in (self.release_receipt, self.debug_receipt):
            self.assertIn(b"\xd0\x90", receipt.read_bytes())
        self.assert_scan_ok()

    def test_skips_malformed_json_before_valid_records(self):
        self.release_receipt.write_bytes(b"{not json}\n" + self.release_receipt.read_bytes())
        self.assert_scan_ok()

    def test_rejects_malformed_required_rlib_record(self):
        _, executable_record = self.release_receipt.read_bytes().splitlines(keepends=True)
        self.release_receipt.write_bytes(b"{not json}\n" + executable_record)
        self.assert_scan_failed("DEV KEY SCAN FAILED: cargo emitted no rlib to scan (release=0, debug=1)")

    def test_rejects_missing_linked_release_executable(self):
        (self.work / RELEASE_EXE).unlink()
        self.assert_scan_failed(
            "DEV KEY SCAN FAILED: expected a linked operator executable in both profiles"
        )

    def test_requires_key_in_debug_rlib(self):
        (self.work / DEBUG_LIB).write_bytes(CLEAN_ARTIFACT)
        self.assert_scan_failed("DEV KEY SCAN FAILED: the key bytes were not found in ANY debug rlib")

    def test_requires_key_in_linked_debug_executable(self):
        (self.work / DEBUG_EXE).write_bytes(CLEAN_ARTIFACT)
        self.assert_scan_failed(
            "DEV KEY SCAN FAILED: the linked debug operator does not contain the development key"
        )

    def test_rejects_key_in_release_rlib(self):
        self.put_key_in(RELEASE_LIB)
        result = self.assert_scan_failed(
            "DEV KEY SCAN FAILED: the development entitlement key is present in a RELEASE artefact"
        )
        self.assertIn(f"dev key present in {RELEASE_LIB}", result.stderr)

    def test_rejects_key_in_linked_release_executable(self):
        self.put_key_in(RELEASE_EXE)
        result = self.assert_scan_failed(
            "DEV KEY SCAN FAILED: the development entitlement key is present in a RELEASE artefact"
        )
        self.assertIn(f"dev key present in {RELEASE_EXE}", result.stderr)

    def test_rejects_invalid_utf8_in_metadata(self):
        receipt = self.release_receipt.read_bytes()
        self.assertIn(b"src/main.rs", receipt)
        self.release_receipt.write_bytes(receipt.replace(b"src/main.rs", b"src/\xff/main.rs"))
        self.assert_scan_failed("UnicodeDecodeError")


if __name__ == "__main__":
    unittest.main()
