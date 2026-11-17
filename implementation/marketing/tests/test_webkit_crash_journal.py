"""Offline CLI and subprocess boundary controls; no tests read a real journal."""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch


COLLECTOR = Path(__file__).resolve().parents[1] / "scripts" / "webkit_crash_journal.py"
BUNDLE_BIN = "/home/runner/.cache/ms-playwright/webkit-2388/minibrowser-wpe/bin"
SINCE = "1794837000"
UNTIL = "1794837060"
CRASH = "1794837031000000"
SECRET = "SyntheticPrivateToken"
ABSOLUTE_PC = "0x00007fbe01234567"


BOOT = "0123456789abcdef0123456789abcdef"
KERNEL_TIME = "1794837031500000"
POSITIVE_KERNEL = (
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 in libWPEWebKit-2.0.so.1[1234,7f0000000000+200000] likely on CPU 2 (core 1, socket 0)',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 in libWPEWebKit-2.0.so.1[7f0000000000+200000] likely on CPU 2 (core -1, socket -1)',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 in libWPEWebKit-2.0.so.1[7f0000000000+200000]',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 likely on CPU 2 (core 1, socket 0)',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4',
)
NEGATIVE_KERNEL = (
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 in libWPEWebKit-2.0.so.1[1234,7f0000000000+200000]',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 likely on CPU 2',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 likely on CPU 2 (core 1, socket 0) SyntheticPrivateToken',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 in /tmp/SyntheticPrivateToken.so[7f0000000000+200000]',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f00000012zz sp 00007fff00001000 error 4',
    'WPEWebProcess[4204]: segfault at 10 ip 00007f0000001234 sp 00007fff00001000 error 4 likely on CPU 2147483648 (core 1, socket 0)',
)


def record(**fields):
    return {
        "COREDUMP_PID": "27625",
        "COREDUMP_SIGNAL_NAME": "SIGABRT",
        "COREDUMP_TIMESTAMP": CRASH,
        "COREDUMP_EXE": f"{BUNDLE_BIN}/WPEWebProcess",
        "COREDUMP_COMM": "WPEWebProcess",
        "MESSAGE": (
            "Process 27625 (WPEWebProcess) crashed and dumped core.\n\n"
            "Stack trace of thread 27625:\n"
            f"#0  {ABSOLUTE_PC} malloc_printerr (libc.so.6 + 0x97259)\n"
            "#1  0x00007fbe48000000 n/a (libWPEWebKit-2.0.so.1 + 0x40ab)\n"
        ),
        **fields,
    }


def jsonl(*items):
    return b"".join(json.dumps(item).encode() + b"\n" for item in items)


class CrashJournalCLI(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        # Even the live-mode tests can only resolve our fixture executable.
        self.env = {"PATH": str(self.tmp)}
        self.fixture("raise SystemExit('unexpected fixture call')")

    def fixture(self, body, *, kernel=False):
        sudo = self.tmp / "sudo"
        guard = "" if kernel else (
            "import sys\nif '_TRANSPORT=kernel' in sys.argv: raise SystemExit(0)\n"
        )
        sudo.write_text(f"#!{sys.executable}\n" + guard + textwrap.dedent(body).lstrip())
        sudo.chmod(0o700)
        return sudo

    def invoke(self, *extra, since=SINCE, until=UNTIL, code=0, bootstrap=None):
        # Make RED about missing CLI behavior, without starting a broken interpreter command.
        self.assertTrue(COLLECTOR.is_file(), "missing WebKit crash journal CLI")
        runner = [sys.executable]
        if not extra and bootstrap is None:
            # The real CLI and query run, but the host kernel setting is never read.
            bootstrap = textwrap.dedent("""
                import builtins, runpy, sys
                original_open = builtins.open

                def fixture_open(path, *args, **kwargs):
                    if path == "/proc/sys/kernel/core_pattern":
                        raise FileNotFoundError
                    return original_open(path, *args, **kwargs)

                builtins.open = fixture_open
                sys.argv.pop(0)
                main = runpy.run_path(sys.argv[0])["main"]
                main.__globals__["installed_identity"] = lambda *args, **kwargs: (None, set())
                main.__globals__["source_receipt"] = lambda *args, **kwargs: dict()
                raise SystemExit(main())
            """)
        if bootstrap is not None:
            runner.extend(("-c", bootstrap))
        result = subprocess.run(
            [*runner, str(COLLECTOR), "--since", since, "--until", until, *extra],
            env=self.env, capture_output=True, timeout=5, check=False,
        )
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.returncode, code)
        self.assertEqual(result.stdout.count(b"\n"), 1)
        self.assertLessEqual(len(result.stdout), 24 * 1024)
        self.assertNotIn(SECRET.encode(), result.stdout)
        self.assertNotIn(ABSOLUTE_PC.encode(), result.stdout)
        self.assertNotIn(b"/home/runner", result.stdout)
        payload = json.loads(result.stdout.decode("ascii"))
        self.assertNotIn(b'"_frame_zero"', result.stdout)
        self.assertNotIn(b'"_boot_id"', result.stdout)
        return payload

    def offline(self, data, *, kernel=None, **kwargs):
        source = self.tmp / f"{SECRET}.jsonl"
        source.write_bytes(data)
        extra = () if kernel is None else ("--kernel-jsonl", str(kernel))
        return self.invoke("--journal-jsonl", str(source), *extra, **kwargs)

    def test_sigabrt_metadata_and_only_safe_stack_evidence(self):
        result = self.offline(jsonl(record()))
        self.assertEqual(result, {
            "schema_version": 2, "availability": "available", "handler": "not_checked",
            "partial": True, "truncated": False, "rejected_records": 0,
            "candidate_scan_complete": True, "export_truncated": False,
            "omission_reasons": ["identity_missing", "symbol_filtered"],
            "records": [{
                "pid": 27625, "timestamp_us": 1794837031000000, "signal": "SIGABRT",
                "role": "web_process", "partial": True, "core_truncated": None,
                "core_storage": "unknown", "module_identity": {},
                "fault_attribution": {"fault_thread": None},
                "threads": [{
                    "tid": 27625, "basis": "listed_only",
                    "frames": [
                        {"ordinal": 0, "module": "libc.so.6", "offset": "0x97259",
                         "symbol": "malloc_printerr"},
                        {"ordinal": 1, "module": "libWPEWebKit-2.0.so.1", "offset": "0x40ab"},
                    ],
                }],
            }],
        })

    def test_replay_preserves_listed_tid_and_original_frame_ordinal(self):
        result = self.offline(jsonl(record(MESSAGE=(
            "Stack trace of thread 4201:\n"
            f"#0  {ABSOLUTE_PC} n/a (lib{SECRET}.so + 0x10)\n"
            f"#1  {ABSOLUTE_PC} n/a (lib{SECRET}.so + 0x11)\n"
            f"#4  {ABSOLUTE_PC} abort (libc.so.6 + 0x12)\n"
            "Stack trace of thread 4204:\n"
            "#0  0x00007f0000001234 n/a (libWPEWebKit-2.0.so.1 + 0x1234)\n"
        ))))
        crash = result["records"][0]
        self.assertEqual(
            [(thread["tid"], [frame["ordinal"] for frame in thread["frames"]])
             for thread in crash.get("threads", [])],
            [(4201, [4]), (4204, [0])],
        )
        self.assertTrue(all(t["basis"] == "listed_only" for t in crash["threads"]))
        self.assertIsNone(crash["fault_attribution"]["fault_thread"])

    def test_replay_preserves_supported_build_ids_and_explicit_core_truncation(self):
        result = self.offline(jsonl(record(
            MESSAGE=record()["MESSAGE"] + "Module libc.so.6, build-id=deadbeef\n",
            COREDUMP_PACKAGE_JSON=json.dumps({
                "libWPEWebKit-2.0.so.1": {"buildId": "0123456789abcdef", "name": SECRET},
            }),
            COREDUMP_TRUNCATED="1", COREDUMP_FILENAME=f"/tmp/{SECRET}",
        )))
        crash = result["records"][0]
        self.assertEqual(crash.get("module_identity", {}), {
            "libc.so.6": "deadbeef", "libWPEWebKit-2.0.so.1": "0123456789abcdef",
        })
        self.assertIs(crash.get("core_truncated"), True)
        self.assertEqual(crash["core_storage"], "external_reported")
        self.assertTrue(result["candidate_scan_complete"])
        self.assertFalse(result["export_truncated"])
        self.assertFalse(result["truncated"])
        for value in ("0", 1, True, None):
            with self.subTest(value=value):
                result = self.offline(jsonl(record(COREDUMP_TRUNCATED=value)))
                self.assertIsNone(result["records"][0]["core_truncated"])

    def test_exact_time_window_and_exact_package_executable_roles(self):
        def row(pid, exe, timestamp=CRASH):
            return record(COREDUMP_PID=str(pid), COREDUMP_TIMESTAMP=timestamp, COREDUMP_EXE=exe)
        result = self.offline(jsonl(
            row(10, f"{BUNDLE_BIN}/WPEWebProcess", "1794836999000000"),
            row(11, f"{BUNDLE_BIN}/WPEWebProcess", "1794837061000000"),
            row(12, "/usr/bin/WPEWebProcess"),
            row(13, f"{BUNDLE_BIN}/../unexpected/WPEWebProcess"),
            row(14, f"{BUNDLE_BIN}/RandomProcess"),
            row(15, "/home/runner/.cache/ms-playwright/webkit-2311/minibrowser-wpe/bin/WPEWebProcess"),
            row(16, f"{BUNDLE_BIN}/MiniBrowser", "1794837000000000"),
            row(17, f"{BUNDLE_BIN}/WPENetworkProcess", "1794837060000000"),
            row(18, f"{BUNDLE_BIN}/WPEGPUProcess"),
        ))
        self.assertEqual(result["rejected_records"], 6)
        self.assertEqual([(r["pid"], r["role"]) for r in result["records"]],
                         [(16, "browser"), (17, "network_process"), (18, "gpu_process")])

    def test_missing_or_non_text_message_remains_partial(self):
        no_message = record()
        no_message.pop("MESSAGE")
        # journalctl JSON can use null for an oversized field or byte arrays for non-printable data.
        result = self.offline(jsonl(no_message, record(MESSAGE=None), record(MESSAGE=[1, 2])))
        self.assertTrue(result["partial"])
        self.assertFalse(result["truncated"])
        self.assertFalse(result["candidate_scan_complete"])
        self.assertIn("join_incomplete", result["omission_reasons"])
        self.assertEqual([(r["partial"], r["threads"]) for r in result["records"]],
                         [(True, []), (True, []), (True, [])])

    def test_empty_and_malformed_are_distinct(self):
        result = self.offline(b"")
        self.assertEqual((result["availability"], result["partial"], result["truncated"],
                          result["rejected_records"]), ("empty", False, False, 0))
        duplicate = jsonl(record()).replace(b'"27625",', b'"27625","COREDUMP_PID":"123",', 1)
        result = self.offline(b'{invalid}\n\xffinvalid\n' + duplicate + jsonl(
            [],
            record(COREDUMP_PID=True),
            record(COREDUMP_PID=27625),
            record(COREDUMP_PID="9999999999"),
            record(COREDUMP_SIGNAL_NAME=[SECRET]),
            record(COREDUMP_SIGNAL_NAME="SIG" + SECRET),
            record(COREDUMP_EXE={SECRET: 1}),
            record(COREDUMP_TIMESTAMP="1794837031"),  # seconds, not the journal field format
        ))
        self.assertEqual((result["availability"], result["partial"], result["truncated"],
                          result["rejected_records"], result["records"]),
                         ("malformed", True, False, 11, []))

    def test_hostile_metadata_and_frame_strings_cannot_escape(self):
        result = self.offline(jsonl(record(
            COREDUMP_COMM=SECRET,
            COREDUMP_CMDLINE=SECRET,
            COREDUMP_ENVIRON=SECRET,
            __CURSOR=SECRET,
            MESSAGE=(
                f"Arbitrary {_token()}\nStack trace of thread 27625:\n"
                f"#0  {ABSOLUTE_PC} {SECRET} (libc.so.6 + 0x10)\n"
                f"#1  {ABSOLUTE_PC} _ZN7WebCore{SECRET} (libc.so.6 + 0x11)\n"
                f"#2  {ABSOLUTE_PC} malloc_printerr({SECRET}) (libc.so.6 + 0x12)\n"
                f"#3  {ABSOLUTE_PC} malloc_printerr (/tmp/{SECRET}/libc.so.6 + 0x13)\n"
                f"#4  {ABSOLUTE_PC} malloc_printerr (lib{SECRET}.so + 0x14)\n"
                f"#5  {ABSOLUTE_PC} malloc_printerr (libc.so.6 + 0x{SECRET})\n"
                f"#6  {ABSOLUTE_PC} malloc_printerr (libc.so.6 + {ABSOLUTE_PC})\n"
                f"#7  {ABSOLUTE_PC} abort (libc.so.6 + 0x15)\n"
            ),
        )))
        self.assertTrue(result["partial"])
        self.assertEqual(result["records"][0]["threads"][0]["frames"], [
            {"ordinal": 0, "module": "libc.so.6", "offset": "0x10"},
            {"ordinal": 1, "module": "libc.so.6", "offset": "0x11"},
            {"ordinal": 2, "module": "libc.so.6", "offset": "0x12"},
            {"ordinal": 7, "module": "libc.so.6", "offset": "0x15", "symbol": "abort"},
        ])

    def test_frame_and_record_caps(self):
        stack = "Stack trace of thread 27625:\n" + "".join(
            f"#{i:<2} {ABSOLUTE_PC} malloc_printerr (libc.so.6 + 0x{i:x})\n"
            for i in range(18)
        )
        result = self.offline(jsonl(*(record(MESSAGE=stack) for _ in range(5))))
        self.assertTrue(result["truncated"])
        self.assertTrue(result["partial"])
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual([len(r["threads"][0]["frames"]) for r in result["records"]], [12] * 3)
        self.assertFalse(result["candidate_scan_complete"])
        self.assertTrue(result["export_truncated"])
        self.assertTrue({"frame_limit", "record_limit", "join_incomplete"}
                        <= set(result["omission_reasons"]))

    def test_raw_cap_and_complete_line_recovery(self):
        prefix = jsonl(record())
        # If the line ending beyond the byte cap is consumed, an extra record is accepted.
        huge = jsonl(record(COREDUMP_PID="111", UNKNOWN=SECRET * 20000))
        result = self.offline(prefix + huge)
        self.assertEqual(result["availability"], "available")
        self.assertTrue(result["truncated"])
        self.assertTrue(result["partial"])
        self.assertEqual([r["pid"] for r in result["records"]], [27625])
        self.assertEqual(result["rejected_records"], 0)
        self.assertFalse(result["candidate_scan_complete"])
        self.assertFalse(result["export_truncated"])
        self.assertTrue({"raw_limit", "join_incomplete"} <= set(result["omission_reasons"]))

    def test_offline_replay_reads_only_the_cap_and_one_probe_byte(self):
        source = self.tmp / "oversized.jsonl"
        source.write_bytes(jsonl(record()) + b"X" * (256 * 1024 + 16384))
        receipt = self.tmp / "byte-offset"
        bootstrap = textwrap.dedent(f"""
            import os, runpy, sys
            from pathlib import Path

            original_open = os.open
            observer = None

            def observe_open(path, *args, **kwargs):
                global observer
                fd = original_open(path, *args, **kwargs)
                if os.fspath(path) == {str(source)!r}:
                    # A duplicate shares the actual file offset past the CLI's close.
                    observer = os.dup(fd)
                return fd

            os.open = observe_open
            sys.argv.pop(0)
            try:
                main = runpy.run_path(sys.argv[0])["main"]
                main.__globals__["installed_identity"] = lambda *args, **kwargs: (None, set())
                raise SystemExit(main())
            finally:
                if observer is not None:
                    Path({str(receipt)!r}).write_text(str(os.lseek(observer, 0, os.SEEK_CUR)))
                    os.close(observer)
        """)
        result = self.invoke("--journal-jsonl", str(source), bootstrap=bootstrap)
        self.assertTrue(result["truncated"])
        self.assertEqual([r["pid"] for r in result["records"]], [27625])
        self.assertEqual(int(receipt.read_text()), 256 * 1024 + 1)

    def test_offline_unavailable_file_never_falls_back_to_journal(self):
        result = self.invoke("--journal-jsonl", str(self.tmp / SECRET))
        self.assertEqual((result["availability"], result["handler"], result["records"]),
                         ("unavailable", "not_checked", []))

    def test_offline_rejects_nonregular_input_without_blocking(self):
        fifo = self.tmp / SECRET
        os.mkfifo(fifo)
        result = self.invoke("--journal-jsonl", str(fifo))
        self.assertEqual(result["availability"], "unavailable")

    def test_bad_windows_safely_fail_validation_before_query(self):
        for since, until in ((SECRET, UNTIL), (SINCE, "inf"), ("-1", UNTIL),
                             (UNTIL, SINCE), (SINCE, "99999999999999999999999")):
            with self.subTest(since=since, until=until):
                result = self.invoke(since=since, until=until, code=2)
                self.assertEqual((result["availability"], result["handler"]),
                                 ("invalid_window", "not_checked"))

    def test_maximum_inclusive_window_is_one_hour(self):
        data = jsonl(record())
        accepted = self.offline(data, until=str(int(SINCE) + 3599))
        self.assertEqual(accepted["availability"], "available")
        rejected = self.offline(data, until=str(int(SINCE) + 3600), code=2)
        self.assertEqual(rejected["availability"], "invalid_window")

    def test_private_index_covers_sixty_four_threads_before_export(self):
        message = "".join(
            f"Stack trace of thread {tid}:\n"
            + "".join(f"#{ordinal} {ABSOLUTE_PC} abort (libc.so.6 + 0x30)\n"
                      for ordinal in range(1, 14))
            + "#0  0x00007f0000001234 n/a (libWPEWebKit-2.0.so.1 + 0x1234)\n"
            for tid in range(4201, 4265)
        )
        collector = runpy.run_path(str(COLLECTOR))
        result = collector["summary"]("available")
        data = jsonl(record(MESSAGE=message, _BOOT_ID="0123456789abcdef0123456789abcdef"))
        collector["collect"](result, data, False, int(SINCE), int(UNTIL))
        self.assertEqual(result["records"][0]["_boot_id"], "0123456789abcdef0123456789abcdef")
        threads = result["records"][0]["threads"]
        self.assertEqual([(t["tid"], t["_listing_index"]) for t in threads],
                         [(tid, tid - 4201) for tid in range(4201, 4265)])
        self.assertEqual([len(t["frames"]) for t in threads], [12] * 64)
        self.assertEqual(threads[-1]["_frame_zero"], {
            "pc": 0x00007f0000001234, "module": "libWPEWebKit-2.0.so.1",
            "frame": {"ordinal": 0, "module": "libWPEWebKit-2.0.so.1", "offset": "0x1234"},
        })
        public = self.offline(data)
        self.assertEqual([t["tid"] for t in public["records"][0]["threads"]], [4201, 4202, 4203])
        self.assertTrue(public["candidate_scan_complete"])
        self.assertTrue(public["export_truncated"])
        self.assertTrue({"frame_limit", "export_limit"} <= set(public["omission_reasons"]))
        self.assertNotIn("00007f0000001234", json.dumps(public))

        overflow = self.offline(jsonl(record(MESSAGE=message + "Stack trace of thread 4265:\n")))
        self.assertFalse(overflow["candidate_scan_complete"])
        self.assertTrue({"thread_limit", "join_incomplete"} <= set(overflow["omission_reasons"]))

    def test_malformed_header_cannot_attach_frame_zero_to_previous_thread(self):
        collector = runpy.run_path(str(COLLECTOR))
        for header in ("Stack trace  of thread 4204:", "Stack\ttrace of thread 4204:"):
            with self.subTest(header=header):
                data = jsonl(record(
                    COREDUMP_SIGNAL_NAME="SIGSEGV",
                    MESSAGE=(
                        "Stack trace of thread 4201:\n"
                        f"#4 {ABSOLUTE_PC} abort (libc.so.6 + 0x12)\n"
                        f"{header}\n"
                        "#0  0x00007f0000001234 n/a (libWPEWebKit-2.0.so.1 + 0x1234)\n"
                    ),
                ))
                result = collector["summary"]("available")
                collector["collect"](result, data, False, int(SINCE), int(UNTIL))
                threads = result["records"][0]["threads"]
                self.assertEqual([(t["tid"], [f["ordinal"] for f in t["frames"]]) for t in threads],
                                 [(4201, [4])])
                self.assertIsNone(threads[0]["_frame_zero"])
                self.assertFalse(result["candidate_scan_complete"])
                self.assertTrue({"malformed", "join_incomplete"} <= set(result["omission_reasons"]))

    def test_unclassifiable_frame_ordinal_invalidates_zero_regardless_of_order(self):
        collector = runpy.run_path(str(COLLECTOR))
        canonical = f"#0 {ABSOLUTE_PC} abort (libc.so.6 + 0x12)\n"
        conflicting = "#\t0  0x00007f0000001234 n/a (libWPEWebKit-2.0.so.1 + 0x1234)\n"
        for frames in (canonical + conflicting, conflicting + canonical):
            with self.subTest(frames=frames):
                data = jsonl(record(
                    COREDUMP_SIGNAL_NAME="SIGSEGV",
                    MESSAGE="Stack trace of thread 4201:\n" + frames,
                ))
                result = collector["summary"]("available")
                collector["collect"](result, data, False, int(SINCE), int(UNTIL))
                thread = result["records"][0]["threads"][0]
                self.assertIsNone(thread["_frame_zero"])
                self.assertEqual(thread["frames"], [])
                self.assertTrue({"malformed", "ordinal_missing"} <= set(result["omission_reasons"]))

    def test_duplicate_tid_and_ordinal_leave_frame_zero_unusable(self):
        first = record()["MESSAGE"]
        cases = [
            (first + "Stack trace of thread 27625:\n" + f"#0 {ABSOLUTE_PC} abort (libc.so.6 + 0x1)\n",
             False),
            (first + f"#0 {ABSOLUTE_PC} abort (libc.so.6 + 0x1)\n", True),
            (first + f" #0 {ABSOLUTE_PC} abort (libc.so.6 + 0x1)\n", True),
        ]
        collector = runpy.run_path(str(COLLECTOR))
        for message, complete in cases:
            with self.subTest(message=message):
                result = collector["summary"]("available")
                collector["collect"](result, jsonl(record(MESSAGE=message)), False, int(SINCE), int(UNTIL))
                self.assertEqual(result["candidate_scan_complete"], complete)
                threads = result["records"][0]["threads"]
                self.assertEqual(len(threads), 1)
                self.assertIsNone(threads[0]["_frame_zero"])
                self.assertNotIn(0, [frame["ordinal"] for frame in threads[0]["frames"]])
                self.assertIn("ordinal_missing", result["omission_reasons"])

    def test_invalid_headers_control_bytes_and_wide_offsets(self):
        result = self.offline(jsonl(record(MESSAGE=(
            "Stack trace of thread 2147483648:\n"
            f"#1 {ABSOLUTE_PC} abort (libc.so.6 + 0x20)\n"
            "Stack trace of thread 999:\r\n"
            f"#2 {ABSOLUTE_PC} abort (libc.so.6 + 0x21)\n"
            "Stack trace of thread 2147483647:\n"
            f"#0 {ABSOLUTE_PC} abort\x00 (libc.so.6 + 0x22)\n"
            f"#999 {ABSOLUTE_PC} abort (libc.so.6 + 0x123456789)\n"
        ))))
        threads = result["records"][0]["threads"]
        self.assertEqual([t["tid"] for t in threads], [2147483647])
        self.assertEqual(threads[0]["frames"], [
            {"ordinal": 999, "module": "libc.so.6", "offset": "0x123456789", "symbol": "abort"},
        ])
        self.assertFalse(result["candidate_scan_complete"])
        self.assertTrue({"malformed", "ordinal_missing", "join_incomplete"}
                        <= set(result["omission_reasons"]))

    def test_conflicting_and_invalid_nested_identities_are_omitted(self):
        result = self.offline(jsonl(record(
            MESSAGE=(record()["MESSAGE"] +
                     "Module libc.so.6, build-id=deadbeef\n" +
                     "Module /usr/lib/x86_64-linux-gnu/libc.so.6, build-id=c01dcafe\n" +
                     "Module libgstreamer-1.0.so.0, build-id=abcdef123\n" +
                     f"Module lib{SECRET}.so, build-id=abcdabcd\n"),
            COREDUMP_PACKAGE_JSON=json.dumps({
                "libc.so.6": {"buildId": "deadbeef"},
                "libgobject-2.0.so.0": {"buildId": "ABCDEF12"},
                "libWPEWebKit-2.0.so.1": {"buildId": "01234567"},
            }),
        ), record(COREDUMP_PACKAGE_JSON=(
            '{"libc.so.6":{"buildId":"deadbeef","buildId":"c01dcafe"}}'
        )), record(COREDUMP_PACKAGE_JSON="[" * 3000 + "]" * 3000)))
        self.assertEqual([r["module_identity"] for r in result["records"]],
                         [{"libWPEWebKit-2.0.so.1": "01234567"}, {}, {}])
        self.assertTrue(result["candidate_scan_complete"])
        self.assertTrue({"identity_conflict", "identity_missing", "malformed", "module_filtered"}
                        <= set(result["omission_reasons"]))

    def test_full_identities_and_stacks_respect_ascii_cap_and_peer_priority(self):
        modules = (
            "libc.so.6", "libsoup-3.0.so.0", "libglib-2.0.so.0", "libgobject-2.0.so.0",
            "libWPEWebKit-2.0.so.1", "libjavascriptcoregtk-4.1.so.0", "libgstreamer-1.0.so.0",
            "libgstbase-1.0.so.0", "libstdc++.so.6", "libgcc_s.so.1", "libpthread.so.0",
            "ld-linux-x86-64.so.2", "MiniBrowser", "WPEWebProcess", "WPENetworkProcess",
            "WPEGPUProcess",
        )
        package = json.dumps({module: {"buildId": "a1" * 64} for module in modules})
        message = "".join(
            f"Stack trace of thread {tid}:\n"
            + "".join(f"#{ordinal} {ABSOLUTE_PC} __pthread_kill_implementation (libc.so.6 + 0x12345678)\n"
                      for ordinal in range(12))
            for tid in range(4201, 4204)
        )
        data = jsonl(*(record(COREDUMP_PID=str(pid), MESSAGE=message, COREDUMP_PACKAGE_JSON=package)
                       for pid in (20, 21, 22)))
        result = self.offline(data)
        self.assertEqual(sum(len(r["module_identity"]) for r in result["records"]), 16)
        self.assertEqual([len(t["frames"]) for r in result["records"] for t in r["threads"]], [12] * 9)
        self.assertFalse(result["export_truncated"])

        # The finite production schema is smaller than the 24 KiB ceiling even at
        # saturation. Lower just the byte budget to exercise its omission order.
        collector = runpy.run_path(str(COLLECTOR))
        indexed = collector["summary"]("available")
        collector["collect"](indexed, data, False, int(SINCE), int(UNTIL))
        indexed["source_receipt"] = {
            "profile": "webkit", "checkout_sha": "a" * 40, "tree_sha": "b" * 40,
            "candidate_source_sha": "c" * 40, "run_id": "9" * 20, "run_attempt": "9" * 20,
            "kernel_release": "x" * 64, "systemd_version": "9" * 10,
            "playwright_version": "1.65.2", "webkit_revision": "2388", "lock_sha256": "f" * 64,
        }
        indexed["kernel_rejection_stage"] = "mixed"
        export = collector["export"]
        full = collector["encode_export"](indexed)
        self.assertLessEqual(len(full) + 1, 24 * 1024)
        export.__globals__["EXPORT_LIMIT"] = len(full) + 1
        self.assertEqual(len(collector["encode_export"](indexed)) + 1, len(full) + 1)
        budget = len(full) + 1 - 100
        export.__globals__["EXPORT_LIMIT"] = budget
        with redirect_stdout(io.StringIO()) as out:
            export(indexed)
        self.assertLessEqual(len(out.getvalue().encode("ascii")), budget)
        small = json.loads(out.getvalue())
        self.assertTrue(small["candidate_scan_complete"])
        self.assertTrue(small["export_truncated"])
        self.assertIn("export_limit", small["omission_reasons"])
        self.assertEqual([r["pid"] for r in small["records"]], [20, 21, 22])
        self.assertEqual([len(t["frames"]) for r in small["records"] for t in r["threads"]][:-1],
                         [12] * 8)
        self.assertLess(len(small["records"][-1]["threads"][-1]["frames"]), 12)

    def test_gpu_profile_admits_only_exact_canonical_regular_parity_binary(self):
        deps = self.tmp.resolve() / "implementation/desktop/target/debug/deps"
        deps.mkdir(parents=True)
        parity = deps / "test_parity-0123456789abcdef"
        parity.write_bytes(b"synthetic fixture")
        escaped = deps / "test_parity-0123456789abcdee"
        escaped.symlink_to(parity)
        suffix = deps / (parity.name + ".debug")
        suffix.write_bytes(b"synthetic fixture")
        directory = deps / "test_parity-0123456789abcded"
        directory.mkdir()
        message = (
            "Stack trace of thread 4201:\n"
            f"#0 {ABSOLUTE_PC} n/a (libvulkan_lvp.so + 0x10)\n"
            f"#1 {ABSOLUTE_PC} n/a ({parity} + 0x11)\n"
            f"#2 {ABSOLUTE_PC} n/a (lib{SECRET}.so + 0x12)\n"
        )
        rows = [record(COREDUMP_EXE=str(path), MESSAGE=message)
                for path in (parity, escaped, suffix, directory, self.tmp / parity.name)]
        rows.extend((record(COREDUMP_EXE=f"{deps}/./{parity.name}"), record()))
        bootstrap = textwrap.dedent(f"""
            from pathlib import Path
            import runpy, sys

            sys.argv.pop(0)
            collector = runpy.run_path(sys.argv[0])
            main = collector["main"]
            main.__globals__["PARITY_DEPS"] = Path({str(deps)!r})
            raise SystemExit(main())
        """)
        source = self.tmp / "gpu-profile.jsonl"
        source.write_bytes(jsonl(*rows))
        result = self.invoke("--profile", "gpu-parity", "--journal-jsonl", str(source), bootstrap=bootstrap)
        self.assertNotIn(str(deps), json.dumps(result))
        self.assertEqual(result["rejected_records"], 6)
        self.assertEqual(len(result["records"]), 1)
        crash = result["records"][0]
        self.assertEqual((crash["role"], crash["executable"]), ("gpu_parity", parity.name))
        self.assertEqual(crash["threads"][0]["frames"], [
            {"ordinal": 0, "module": "libvulkan_lvp.so", "offset": "0x10"},
            {"ordinal": 1, "module": parity.name, "offset": "0x11"},
        ])
        self.assertIn("module_filtered", result["omission_reasons"])

    def test_live_query_uses_fixed_read_only_argv_and_real_output_boundary(self):
        receipt = self.tmp / "argv"
        long_message = (SECRET * 300 + "\\n" + record()["MESSAGE"]).replace(
            "libWPEWebKit-2.0.so.1 +",
            f"{BUNDLE_BIN.removesuffix('/bin')}/lib/libWPEWebKit-2.0.so.1.10.2 +",
        )
        self.assertGreater(len(long_message.encode()), 4096)
        self.fixture(f"""
            import json, os, sys
            from pathlib import Path
            Path({str(receipt)!r}).write_text(json.dumps([sys.argv[1:], os.getpid(), os.getpgrp()]))
            sys.stderr.write({SECRET!r})
            # Model journalctl's null encoding above the default JSON field limit.
            sys.stdout.buffer.write({jsonl(record(MESSAGE=long_message))!r} if "--all" in sys.argv
                                    else {jsonl(record(MESSAGE=None))!r})
        """)
        result = self.invoke()
        self.assertEqual([r["pid"] for r in result["records"]], [27625])
        self.assertEqual(result["records"][0]["threads"][0]["frames"], [
            {"ordinal": 0, "module": "libc.so.6", "offset": "0x97259", "symbol": "malloc_printerr"},
            {"ordinal": 1, "module": "libWPEWebKit-2.0.so.1", "offset": "0x40ab"},
        ])
        self.assertIn(result["handler"], ("systemd_coredump", "other_pipe", "file", "unavailable"))
        args, pid, group = json.loads(receipt.read_text())
        self.assertEqual(pid, group)
        self.assertNotEqual(group, os.getpgrp())
        self.assertEqual(args, [
            "-n", "journalctl", "-b", "--no-pager", "--quiet", "--all",
            "--since", "@1794837000", "--until", "@1794837060.999999",
            "MESSAGE_ID=fc2e22bc6ee647b6b90729ab34a250b1", "-o", "json",
            "--output-fields=COREDUMP_TIMESTAMP,COREDUMP_PID,COREDUMP_SIGNAL_NAME,"
            "COREDUMP_EXE,COREDUMP_COMM,MESSAGE,_BOOT_ID,COREDUMP_TRUNCATED,"
            "COREDUMP_FILENAME,COREDUMP_PACKAGE_JSON",
        ])

    def test_live_command_unavailable_or_denied_never_prints_diagnostics(self):
        self.fixture(f"""
            import sys
            sys.stderr.write({SECRET!r})
            sys.stdout.buffer.write({jsonl(record())!r})
            raise SystemExit(1)
        """)
        result = self.invoke()
        self.assertEqual((result["availability"], result["records"]), ("unavailable", []))
        (self.tmp / "sudo").unlink()
        result = self.invoke()
        self.assertEqual(result["availability"], "unavailable")

    def assert_stopped(self, marker):
        pid, group = map(int, marker.read_text().split())
        self.assertEqual(pid, group)
        self.assertNotEqual(group, os.getpgrp())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_live_byte_overflow_keeps_only_complete_lines_and_reaps_command(self):
        marker = self.tmp / "overflow-process"
        self.fixture(f"""
            import os, time
            from pathlib import Path
            Path({str(marker)!r}).write_text(f'{{os.getpid()}} {{os.getpgrp()}}')
            os.write(1, {jsonl(record())!r})
            for _ in range(33):
                os.write(1, b"X" * 8192)
            time.sleep(4)
        """)
        result = self.invoke()
        self.assertTrue(result["truncated"])
        self.assertEqual([r["pid"] for r in result["records"]], [27625])
        self.assert_stopped(marker)

    def test_live_timeout_ends_its_own_group_even_if_a_descendant_keeps_pipe_open(self):
        marker = self.tmp / "timeout-process"
        survivor = self.tmp / "descendant-survived"
        self.fixture(f"""
            import os, signal, time
            from pathlib import Path
            if os.fork() == 0:
                # Keep stdout open and ignore graceful termination, like a stuck child.
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                time.sleep(4.55)
                Path({str(survivor)!r}).touch()
                os._exit(0)
            Path({str(marker)!r}).write_text(f'{{os.getpid()}} {{os.getpgrp()}}')
            time.sleep(4.85)
        """)
        started = time.monotonic()
        result = self.invoke()
        self.assertEqual(result["availability"], "timeout")
        self.assertTrue(result["partial"])
        self.assertFalse(result["candidate_scan_complete"])
        self.assertTrue({"deadline", "join_incomplete"} <= set(result["omission_reasons"]))
        self.assert_stopped(marker)
        time.sleep(max(0, 4.95 - (time.monotonic() - started)))
        self.assertFalse(survivor.exists())


def kernel_row(message=POSITIVE_KERNEL[0], **fields):
    return {"MESSAGE": message, "__REALTIME_TIMESTAMP": KERNEL_TIME, "_BOOT_ID": BOOT,
            "_TRANSPORT": "kernel", **fields}


def joining_record(listing=4, *, zero=None, total=None, **fields):
    tids = [tid for tid in range(4300, 4300 + (total or listing) - 1)]
    tids.insert(listing - 1, 4204)
    for index in range(min(3, listing - 1)):
        tids[index] = 4201 + index
    zero = zero if zero is not None else (
        "#0  0x00007f0000001234 n/a (libWPEWebKit-2.0.so.1 + 0x1234)\n"
    )
    msg = "".join(
        f"Stack trace of thread {tid}:\n"
        + (zero if tid == 4204 else f"#0  0x{0x7f0000003000 + tid:016x} abort (libc.so.6 + 0x10)\n")
        for tid in tids
    )
    return record(**{"COREDUMP_PID": "4201", "COREDUMP_SIGNAL_NAME": "SIGSEGV",
                     "MESSAGE": msg, "_BOOT_ID": BOOT, **fields})


def elf_fixture(ids=(b"\x12\x34\x56\x78",), *, klass=2, machine=62,
                note_offset=120, note_size=None, phnum=1, padded_note_size=None):
    notes = b"".join(
        struct.pack("<III", 4, len(value), 3) + b"GNU\0" + value + bytes(-len(value) % 4)
        for value in ids
    )
    if padded_note_size is not None:
        # A second, non-build-ID note fills the segment with valid records.
        padding = padded_note_size - len(notes) - 16
        assert padding >= 0 and padding % 4 == 0
        notes += struct.pack("<III", 4, padding, 1) + b"TST\0" + bytes(padding)
    header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF" + bytes((klass, 1, 1)) + bytes(9),
                         3, machine, 1, 0, 64, 0, 0, 64, 56, phnum, 0, 0, 0)
    segment = struct.pack("<IIQQQQQQ", 4, 4, note_offset, 0, 0,
                          len(notes) if note_size is None else note_size, len(notes), 4)
    return header + (segment + notes if phnum else b"")


class KernelCorrelation(unittest.TestCase):
    fixture = CrashJournalCLI.fixture
    invoke = CrashJournalCLI.invoke
    offline = CrashJournalCLI.offline
    assert_stopped = CrashJournalCLI.assert_stopped

    def setUp(self):
        CrashJournalCLI.setUp(self)
        self.collector = runpy.run_path(str(COLLECTOR))

    def correlated(self, crashes, kernel, *, cut=False, budget=None, additions=None):
        result = self.collector["summary"]("available")
        self.collector["collect"](result, crashes, cut, int(SINCE), int(UNTIL))
        records, complete, reasons = self.collector["correlate_kernel"](
            result["records"], kernel, result["candidate_scan_complete"],
        )
        result.update(records=records, candidate_scan_complete=complete,
                      omission_reasons=sorted({*result["omission_reasons"], *reasons}))
        if additions:
            result.update(additions)
        output = io.StringIO()
        export = self.collector["export"]
        limit = export.__globals__["EXPORT_LIMIT"]
        try:
            if budget is not None:
                export.__globals__["EXPORT_LIMIT"] = budget
            with redirect_stdout(output):
                export(result)
        finally:
            export.__globals__["EXPORT_LIMIT"] = limit
        raw = output.getvalue().encode("ascii")
        self.assertLessEqual(len(raw), budget or 24 * 1024)
        for private in (b"00007f0000001234", BOOT.encode(), b"segfault at", SECRET.encode(),
                        b"/home/runner", b"_listing_index", b"_frame_zero", b"_parity_exe"):
            self.assertNotIn(private, raw)
        return json.loads(raw)

    def assert_unknown(self, result, reason, *, complete=False):
        self.assertEqual(result["candidate_scan_complete"], complete)
        self.assertIn(reason, result["omission_reasons"])
        for crash in result["records"]:
            self.assertIsNone(crash["fault_attribution"]["fault_thread"])
        if not complete:
            self.assertIn("join_incomplete", result["omission_reasons"])

    def rejected_stage(self, messages, *, availability="available"):
        result = self.collector["summary"]("available")
        self.collector["collect"](result, jsonl(joining_record()), False, int(SINCE), int(UNTIL))
        self.collector["attach_kernel"](
            result, availability, jsonl(*(kernel_row(message) for message in messages)), False, True,
        )
        raw = self.collector["encode_export"](result)
        self.assertNotIn(SECRET, raw)
        self.assertNotIn("00007f0000001234", raw)
        return json.loads(raw)

    def test_refused_alias_observation_preserves_refusal_and_listed_order(self):
        alias = "libWPEWebKit-2.0.so.1.10.2"
        message = POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", alias)
        self.assertEqual(self.collector["_parse_kernel_message"](message), (None, "module_policy"))
        result = self.rejected_stage([message])
        self.assert_unknown(result, "kernel_unsupported_format")
        self.assertEqual(result["kernel_rejection_stage"], "module_policy")
        self.assertEqual([t["tid"] for t in result["records"][0]["threads"]], [4201, 4202, 4203])
        expected_counts = dict(structurally_invalid=0, no_retained_candidate=0,
                               one_retained_candidate=1, multiple_retained_candidates=0,
                               indeterminate=0)
        observation = result.get("kernel_module_policy_observation")
        self.assertIsNotNone(observation, "module-policy refusal lost its finite observation")
        self.assertEqual(observation["buckets"]["unknown_alias"], expected_counts)
        self.assertEqual(observation["coverage"], "complete")
        self.assertEqual(observation["alias_resolution"], "unavailable")
        self.assertNotIn(alias, json.dumps(result))

    def test_module_policy_masks_invalid_ending_and_range_without_private_match(self):
        alias = "libWPEWebKit-2.0.so.1.10.2"
        for message in (NEGATIVE_KERNEL[0], NEGATIVE_KERNEL[5].replace(
                "error 4", "error 4 in libWPEWebKit-2.0.so.1[7f0000000000+200000]")):
            message = message.replace("libWPEWebKit-2.0.so.1", alias)
            with self.subTest(message=message):
                self.assertEqual(self.collector["_parse_kernel_message"](message), (None, "module_policy"))
                result = self.rejected_stage([message])
                self.assert_unknown(result, "kernel_unsupported_format")
                observation = result.get("kernel_module_policy_observation")
                self.assertIsNotNone(observation, "masked invalid refusal lost its observation")
                self.assertEqual(observation["buckets"]["unknown_alias"], dict(
                    structurally_invalid=1, no_retained_candidate=0, one_retained_candidate=0,
                    multiple_retained_candidates=0, indeterminate=0))

    def observation_result(self, crashes, rows, *, cut=False, kernel_cut=False,
                           availability="available", reaped=True, profile="webkit"):
        result = self.collector["summary"]("available")
        self.collector["collect"](result, crashes, cut, int(SINCE), int(UNTIL), profile=profile)
        self.collector["attach_kernel"](result, availability, rows, kernel_cut, reaped)
        return result, json.loads(self.collector["encode_export"](result))

    def test_private_relation_preserves_candidate_boundaries(self):
        alias = "libWPEWebKit-2.0.so.1.10.2"
        message = POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", alias)
        zero = "#0  0x00007f0000001234 n/a (libWPEWebKit-2.0.so.1 + 0x1234)\n"
        cases = [
            (jsonl(joining_record(4)), kernel_row(message), "one_retained_candidate"),
            (jsonl(joining_record(64)), kernel_row(message), "one_retained_candidate"),
            (jsonl(joining_record(65)), kernel_row(message), "no_retained_candidate"),
            (jsonl(joining_record()), kernel_row(message.replace("[4204]", "[4205]")), "no_retained_candidate"),
            (jsonl(joining_record()), kernel_row(message.replace("00007f0000001234", "00007f0000001235")), "no_retained_candidate"),
            (jsonl(joining_record()), kernel_row(message, _BOOT_ID="f" * 32), "no_retained_candidate"),
            (jsonl(joining_record(COREDUMP_SIGNAL_NAME="SIGABRT")), kernel_row(message), "no_retained_candidate"),
            (jsonl(joining_record(_BOOT_ID=None)), kernel_row(message), "indeterminate"),
            (jsonl(joining_record(), joining_record(_BOOT_ID=None)), kernel_row(message), "indeterminate"),
            (jsonl(joining_record(), joining_record()), kernel_row(message), "multiple_retained_candidates"),
            (jsonl(joining_record(), joining_record(MESSAGE=zero)), kernel_row(message), "one_retained_candidate"),
            (jsonl(record(), record(), record(), joining_record()), kernel_row(message), "no_retained_candidate"),
        ]
        for offset, relation in ((-1, "no_retained_candidate"), (0, "one_retained_candidate"),
                                 (1999999, "one_retained_candidate"), (2000000, "no_retained_candidate")):
            cases.append((jsonl(joining_record()), kernel_row(message, __REALTIME_TIMESTAMP=str(int(CRASH)+offset)), relation))
        for bad_zero in (zero.replace("#0", "#4"), zero.replace("libWPEWebKit-2.0.so.1", SECRET),
                         zero+zero, zero+zero.replace("1234", "1235")):
            cases.append((jsonl(joining_record(zero=bad_zero)), kernel_row(message), "indeterminate"))
            # Time and boot exclusions precede checking unavailable original #0.
            cases.append((jsonl(joining_record(zero=bad_zero)), kernel_row(message, __REALTIME_TIMESTAMP=str(int(CRASH)-1)), "no_retained_candidate"))
            cases.append((jsonl(joining_record(zero=bad_zero)), kernel_row(message, _BOOT_ID="f"*32), "no_retained_candidate"))
        for crashes, row, relation in cases:
            with self.subTest(relation=relation, row=row):
                _, result = self.observation_result(crashes, jsonl(row))
                self.assert_unknown(result, "kernel_unsupported_format")
                observation = result.get("kernel_module_policy_observation")
                self.assertIsNotNone(observation)
                self.assertEqual(observation["buckets"]["unknown_alias"][relation], 1)
                self.assertEqual(sum(observation["buckets"]["unknown_alias"].values()), 1)
                self.assertEqual(observation["coverage"], "complete")
                for record_ in result["records"]:
                    self.assertTrue(all(t["basis"] == "listed_only" for t in record_["threads"]))

    def test_observation_coverage_is_independent_of_candidate_completeness(self):
        message = POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", SECRET)
        k = jsonl(kernel_row(message))
        for crashes, rows, options, coverage, matches in (
            (jsonl(joining_record()), k, {}, "complete", 1),
            (jsonl(joining_record(65)), k, {}, "complete", 0),
            (jsonl(record(), record(), record(), joining_record()), k, {}, "complete", 0),
            (jsonl(joining_record()), k, {"cut": True}, "partial", 1),
            (jsonl(joining_record()), k, {"kernel_cut": True}, "partial", 1),
            (jsonl(joining_record()), k, {"availability": "timeout"}, "partial", 1),
            (jsonl(joining_record()), k, {"reaped": False}, "partial", 1),
            (jsonl(joining_record()), k+b'{broken\n', {}, "partial", 1),
            (jsonl(joining_record()), k+jsonl(kernel_row(MESSAGE=None)), {}, "partial", 1),
            (jsonl(joining_record()), k+b"\n"*(64*1024), {}, "partial", 1),
        ):
            with self.subTest(options=options, coverage=coverage):
                _, result = self.observation_result(crashes, rows, **options)
                self.assert_unknown(result, "kernel_unsupported_format")
                observation = result.get("kernel_module_policy_observation")
                self.assertIsNotNone(observation)
                self.assertEqual(observation["coverage"], coverage)
                self.assertEqual(observation["buckets"]["other_rejected"]["one_retained_candidate"],
                                 matches)

    def test_alias_slots_saturation_and_exact_installed_spelling(self):
        aliases = [f"libWPEWebKit-2.0.so.1.{i}" for i in range(1, 10)]
        def rows(tokens):
            return jsonl(*(kernel_row(POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", token))
                           for token in tokens))
        for count in (8, 9):
            state, result = self.observation_result(jsonl(joining_record()), rows(aliases[:count] + aliases[:1]*4))
            pending = state["_module_rejections"]
            self.assertEqual(len(pending["aliases"]), 8)
            self.assertTrue(all(len(token.encode("ascii")) <= 64 for token in pending["aliases"]))
            for resolved, bucket, amount in ((None, "unknown_alias", 2),
                                            (aliases[0], "resolved_wpe_alias", 2),
                                            (aliases[-1], "resolved_wpe_alias", 0),
                                            ("libWPEWebKit-2.0.so.1", "resolved_wpe_alias", 0)):
                with self.subTest(count=count, resolved=resolved):
                    summary = self.collector["_finalize_module_rejections"](pending, resolved)
                    self.assertEqual(summary["buckets"][bucket]["one_retained_candidate"], amount)
                    self.assertEqual(summary["pending_alias_limit_hit"], count == 9)
                    self.assertEqual(summary["coverage"], "partial" if count == 9 else "complete")
                    if resolved is not None:
                        self.assertEqual(summary["buckets"]["other_rejected"]["one_retained_candidate"], 2)
                        self.assertEqual(summary["buckets"]["unknown_alias"]["one_retained_candidate"], int(count == 9))
                    state["kernel_module_policy_observation"] = summary
                    raw = self.collector["encode_export"](state)
                    for token in (*aliases, SECRET, BOOT, "00007f0000001234", "_module_rejections"):
                        self.assertNotIn(token, json.dumps(json.loads(raw)["kernel_module_policy_observation"]))
                    self.assertLessEqual(len(json.dumps(summary, separators=(",", ":"))), 1024)
            # No finalization may relabel/evict the retained slots.
            self.assertEqual(list(pending["aliases"]), aliases[:8])
        for token in (SECRET, "libc.so.6.1", "libWPEWebKit-2.0.so.1." + "1"*43,
                      "libWPEWebKit-2.0.so.1." + "1"*44):
            state, result = self.observation_result(jsonl(joining_record()), rows([token]*3))
            self.assertEqual(state["_module_rejections"]["aliases"], {})
            self.assertEqual(result["kernel_module_policy_observation"]["buckets"]["other_rejected"]["one_retained_candidate"], 2)

    def test_profile_exclusion_is_explicit_even_with_no_parity_records(self):
        rejected = jsonl(kernel_row(POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", SECRET)))
        state, result = self.observation_result(b"", rejected, profile="gpu-parity")
        self.assertNotIn("kernel_module_policy_observation", result)
        self.assertNotIn("_module_rejections", state)
        diagnostics = {}
        self.collector["correlate_kernel"]([], rejected, True, diagnostics=diagnostics, profile="gpu-parity")
        self.assertEqual(diagnostics, {"kernel_rejection_stage": "module_policy"})
        # The profile remains authoritative at export, including hostile optional input.
        state["kernel_module_policy_observation"] = {"raw": SECRET}
        self.assertEqual(json.loads(self.collector["encode_export"](state)), result)

    def test_private_comparison_error_is_partial_without_changing_refusal(self):
        compare = self.collector["_kernel_candidate_check"]
        def broken(*args, **kwargs):
            if not kwargs["compare_module"]:
                raise ValueError(SECRET)
            return compare(*args, **kwargs)
        with patch.dict(self.collector["correlate_kernel"].__globals__, _kernel_candidate_check=broken):
            result = self.rejected_stage([POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", SECRET)])
        self.assert_unknown(result, "kernel_unsupported_format")
        observation = result["kernel_module_policy_observation"]
        self.assertEqual(observation["coverage"], "partial")
        self.assertEqual(observation["buckets"]["other_rejected"]["indeterminate"], 1)

    def test_observation_export_rejects_wrong_types_extra_keys_and_caps(self):
        state, _ = self.observation_result(jsonl(joining_record()), jsonl(kernel_row(
            POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", SECRET))))
        valid = state["kernel_module_policy_observation"]
        encode = self.collector["encode_export"]
        baseline = json.loads(encode(state))
        invalids = [None, [], {**valid, "private": SECRET}, {**valid, "version": True},
                    {**valid, "version": 2}, {**valid, "coverage": SECRET},
                    {**valid, "coverage": []}, {**valid, "alias_resolution": SECRET},
                    {**valid, "pending_alias_limit_hit": 1},
                    {**valid, "buckets": {**valid["buckets"], SECRET: {}}}]
        for bad in (True, -1, 3, 1.0, "1", None):
            mutant = copy.deepcopy(valid)
            mutant["buckets"]["other_rejected"]["one_retained_candidate"] = bad
            invalids.append(mutant)
        for bad in invalids:
            state["kernel_module_policy_observation"] = bad
            result = json.loads(encode(state))
            expected = {k: v for k, v in baseline.items() if k != "kernel_module_policy_observation"}
            expected["partial"] = True
            self.assertEqual(result, expected)
            self.assertNotIn(SECRET, encode(state))
        state["kernel_module_policy_observation"] = valid
        size = len(json.dumps(valid, separators=(",", ":"), ensure_ascii=True))
        for limit, retained in ((size, True), (size-1, False)):
            with patch.dict(encode.__globals__, MODULE_OBSERVATION_LIMIT=limit):
                result = json.loads(encode(state))
                self.assertEqual("kernel_module_policy_observation" in result, retained)
        timeout = json.loads(self.collector["encode_timeout"](state))
        self.assertNotIn("kernel_module_policy_observation", timeout)
        self.assert_unknown(timeout, "deadline")

    def test_observation_consumes_existing_budget_without_displacing_proven_zero(self):
        # Add the independently valid optional object to an accepted-attribution
        # result to exercise export priority without treating a refusal as proof.
        _, rejected = self.observation_result(jsonl(joining_record()), jsonl(kernel_row(
            POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", SECRET))))
        additions = {"kernel_module_policy_observation": rejected["kernel_module_policy_observation"]}
        baseline = self.correlated(jsonl(record(), joining_record()), jsonl(kernel_row()), additions=additions)
        size = len(json.dumps(baseline, separators=(",", ":")))+1
        result = self.correlated(jsonl(record(), joining_record()), jsonl(kernel_row()), budget=size-190,
                                 additions=additions)
        selected = next(r for r in result["records"] if r["pid"] == 4201)
        self.assertEqual(selected["fault_attribution"]["fault_thread"]["tid"], 4204)
        self.assertEqual(selected["threads"][0]["frames"][0]["ordinal"], 0)
        self.assertEqual(result["kernel_module_policy_observation"], additions["kernel_module_policy_observation"])
        self.assertTrue(result["export_truncated"])
        self.assertTrue(result["candidate_scan_complete"])

    def test_observation_failure_does_not_interrupt_original_refusal(self):
        def broken(*args):
            raise ValueError(SECRET)
        with patch.dict(self.collector["correlate_kernel"].__globals__, _observe_module_rejection=broken):
            try:
                result = self.rejected_stage([POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", SECRET)])
            except ValueError:
                self.fail("optional observation error escaped into accepted collector behavior")
        self.assert_unknown(result, "kernel_unsupported_format")
        observation = result.get("kernel_module_policy_observation")
        self.assertIsNotNone(observation)
        self.assertEqual(observation["coverage"], "partial")

    def test_single_parse_and_masked_invalid_rows_never_compare_candidates(self):
        parse = self.collector["_kernel_message_details"]
        compare = self.collector["_kernel_candidate_check"]
        parsed, comparisons = [], []
        def observed_parse(message, parity_names=()):
            parsed.append(message)
            return parse(message, parity_names)
        def observed_compare(*args, **kwargs):
            comparisons.append(kwargs["compare_module"])
            return compare(*args, **kwargs)
        messages = [NEGATIVE_KERNEL[0], POSITIVE_KERNEL[0].replace("core 1", "core -2147483649"),
                    POSITIVE_KERNEL[0].replace("socket 0", "socket 2147483648")]
        messages = [m.replace("libWPEWebKit-2.0.so.1", SECRET) for m in messages]
        with patch.dict(self.collector["correlate_kernel"].__globals__,
                        _kernel_message_details=observed_parse, _kernel_candidate_check=observed_compare):
            result = self.rejected_stage(messages)
        self.assertEqual(parsed, messages)
        self.assertEqual(comparisons, [])
        self.assertEqual(result["kernel_rejection_stage"], "module_policy")
        self.assertEqual(result["kernel_module_policy_observation"]["buckets"]["other_rejected"]["structurally_invalid"], 2)

    def test_main_finalizes_once_after_existing_identity_and_offline_never_probes(self):
        main = self.collector["main"]
        globals_ = main.__globals__
        alias = "libWPEWebKit-2.0.so.1.10.2"
        crashes = jsonl(joining_record())
        rows = jsonl(kernel_row(POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", alias)))
        outputs, children = [], []
        def child(args, limit, read_deadline, cleanup_deadline):
            children.append((limit, read_deadline, cleanup_deadline))
            return "available", json.dumps({"sha256": "a"*64, "build_id": None,
                                             "_resolved_basename": alias}).encode(), False, True
        overrides = dict(write_export=lambda encoded, deadline: outputs.append(json.loads(encoded)),
                         core_handler=lambda: "not_checked", query=lambda *args: ("available", crashes, False, True),
                         query_kernel=lambda *args: ("available", rows, False, True),
                         source_receipt=lambda *args, **kwargs: {}, read_child=child)
        args = [str(COLLECTOR), "--since", SINCE, "--until", UNTIL]
        with patch.dict(globals_, overrides), patch.object(sys, "argv", args):
            self.assertEqual(main(), 0)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0][0], 1024)
        self.assertAlmostEqual(children[0][2]-children[0][1], 0.65)
        self.assert_unknown(outputs[-1], "kernel_unsupported_format")
        self.assertEqual(outputs[-1]["kernel_module_policy_observation"]["buckets"]["resolved_wpe_alias"]["one_retained_candidate"], 1)
        self.assertNotIn(alias, json.dumps(outputs[-1]))
        crash_path, kernel_path = self.tmp / "observation-crash", self.tmp / "observation-kernel"
        crash_path.write_bytes(crashes)
        kernel_path.write_bytes(rows)
        def forbidden(*args, **kwargs):
            self.fail("offline rejected-row observation consulted the host")
        overrides.update({key: forbidden for key in ("core_handler", "query", "query_kernel", "source_receipt", "read_child", "installed_identity")})
        with patch.dict(globals_, overrides), patch.object(sys, "argv", args + [
                "--journal-jsonl", str(crash_path), "--kernel-jsonl", str(kernel_path)]):
            self.assertEqual(main(), 0)
        self.assertEqual(outputs[-1]["kernel_module_policy_observation"]["alias_resolution"], "unavailable")
        self.assertEqual(outputs[-1]["kernel_module_policy_observation"]["buckets"]["unknown_alias"]["one_retained_candidate"], 1)
        self.assertEqual(len(children), 1)

    def test_finalization_deadline_uses_existing_safe_fallback_without_retry(self):
        main = self.collector["main"]
        globals_ = main.__globals__
        finalize = globals_["_finalize_module_rejections"]
        calls, outputs = [], []
        def expired(state, basename):
            calls.append(basename)
            if len(calls) == 2:
                raise globals_["DiagnosticDeadline"]
            return finalize(state, basename)
        overrides = dict(write_export=lambda encoded, deadline: outputs.append(json.loads(encoded)),
                         core_handler=lambda: "not_checked",
                         query=lambda *args: ("available", jsonl(joining_record()), False, True),
                         query_kernel=lambda *args: ("available", jsonl(kernel_row(POSITIVE_KERNEL[0].replace(
                             "libWPEWebKit-2.0.so.1", SECRET))), False, True),
                         source_receipt=lambda *args, **kwargs: {},
                         installed_identity=lambda *args, **kwargs: (None, {"identity_missing"}),
                         _finalize_module_rejections=expired)
        with patch.dict(globals_, overrides), patch.object(sys, "argv", [str(COLLECTOR), "--since", SINCE, "--until", UNTIL]):
            self.assertEqual(main(), 0)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("kernel_module_policy_observation", outputs[-1])
        self.assert_unknown(outputs[-1], "deadline")

    def test_kernel_rejection_stage_classifies_existing_branches(self):
        # A missing/wrong branch code must fail independently of the refusal itself.
        cases = (
            (POSITIVE_KERNEL[0] + "é", "text_bounds"),
            ("segfault " + SECRET, "prefix_shape"),
            (POSITIVE_KERNEL[0].replace("4204", "2147483648"), "numeric_range"),
            (NEGATIVE_KERNEL[1], "suffix_shape"),
            (POSITIVE_KERNEL[2].replace("libWPEWebKit-2.0.so.1", SECRET), "module_policy"),
            (NEGATIVE_KERNEL[0], "producer_ending"),
            (NEGATIVE_KERNEL[5], "numeric_range"),
        )
        for message, stage in cases:
            with self.subTest(stage=stage):
                result = self.rejected_stage([message])
                self.assertEqual(result.get("kernel_rejection_stage"), stage)
                self.assert_unknown(result, "kernel_unsupported_format")

    def test_kernel_rejection_stage_aggregates_without_event_details(self):
        a, b = NEGATIVE_KERNEL[0], "segfault " + SECRET
        for messages, expected in (([a, a], "producer_ending"), ([a, b, a], "mixed")):
            result = self.rejected_stage(messages)
            self.assertEqual(result.get("kernel_rejection_stage"), expected)
            self.assert_unknown(result, "kernel_unsupported_format")
            self.assertNotIn("kernel_events", result)

    def test_kernel_rejection_stage_absent_without_unsupported_text(self):
        for messages, availability in ((POSITIVE_KERNEL, "available"), ([], "unavailable"),
                                       ([None], "available"), (["ordinary " + SECRET], "available")):
            result = self.rejected_stage(messages, availability=availability)
            self.assertNotIn("kernel_rejection_stage", result)

    def test_literal_kernel_grammar(self):
        parse = self.collector["parse_kernel_message"]
        for i, fixture in enumerate(POSITIVE_KERNEL):
            with self.subTest(positive=i):
                expected = (4204, 0x00007f0000001234, "libWPEWebKit-2.0.so.1" if i < 3 else None)
                self.assertEqual(parse(fixture), expected)
                self.assertEqual(parse(fixture + "\n"), expected)
        for fixture in (
            *NEGATIVE_KERNEL, POSITIVE_KERNEL[0] + "\n\n", POSITIVE_KERNEL[0] + "\r\n",
            POSITIVE_KERNEL[0].replace("WPEWebProcess", "x" * 65),
            POSITIVE_KERNEL[0].replace("WPEWebProcess", "xé"),
            POSITIVE_KERNEL[0].replace("4204", "2147483648"),
            POSITIVE_KERNEL[0].replace("4204", "0"),
            POSITIVE_KERNEL[0].replace("core 1", "core -2147483649"),
            POSITIVE_KERNEL[0].replace("socket 0", "socket +0"),
            POSITIVE_KERNEL[0].replace("error 4", "error " + "1" * 17),
            POSITIVE_KERNEL[0].replace("sp 00007fff00001000", "sp 7fff00001000"),
            POSITIVE_KERNEL[0].replace("at 10", "at 0x10"),
            POSITIVE_KERNEL[0].replace("1234,7f", "ABCD,7f"),
        ):
            with self.subTest(fixture=fixture):
                self.assertIsNone(parse(fixture))

    def test_fault_stack_selected_after_all_thread_headers(self):
        for listing in (4, 64):
            with self.subTest(listing=listing):
                result = self.correlated(jsonl(joining_record(listing)), jsonl(kernel_row()))
                self.assertTrue(result["candidate_scan_complete"])
                self.assertTrue(result["export_truncated"])
                crash = result["records"][0]
                self.assertEqual([t["tid"] for t in crash["threads"]], [4204, 4201, 4202])
                self.assertEqual(crash["fault_attribution"]["fault_thread"], {
                    "tid": 4204, "basis": "kernel_tid_and_frame0_pc", "delta_us": 500_000,
                    "frame_zero": {"ordinal": 0, "module": "libWPEWebKit-2.0.so.1", "offset": "0x1234"},
                })
                self.assertEqual(crash["threads"][0]["basis"], "kernel_tid_and_frame0_pc")

    def test_wrong_join_keys_remain_unknown(self):
        for row in (
            kernel_row(POSITIVE_KERNEL[0].replace("00007f0000001234", "00007f0000001235")),
            kernel_row(POSITIVE_KERNEL[0].replace("[4204]", "[4205]")),
            kernel_row(POSITIVE_KERNEL[0].replace("libWPEWebKit-2.0.so.1", "libc.so.6")),
            kernel_row(__REALTIME_TIMESTAMP="1794837030999999"),
            kernel_row(__REALTIME_TIMESTAMP="1794837033000000"),
            kernel_row(_BOOT_ID="1123456789abcdef0123456789abcdef"),
        ):
            with self.subTest(row=row):
                self.assert_unknown(self.correlated(jsonl(joining_record()), jsonl(row)),
                                    "kernel_no_match", complete=True)
        self.assert_unknown(
            self.correlated(jsonl(joining_record(COREDUMP_SIGNAL_NAME="SIGABRT")), jsonl(kernel_row())),
            "kernel_no_match", complete=True,
        )

    def test_incomplete_inputs_cannot_prove_unique_fault(self):
        crash = jsonl(joining_record())
        k = jsonl(kernel_row())
        past = (jsonl(record(COREDUMP_TIMESTAMP="1794836999000000")) * 3)
        next_crash = jsonl(joining_record(COREDUMP_PID="4250"))
        pad_dump = 256 * 1024 - len(crash) - len(past) - len(next_crash) // 2
        clipped_crash = crash + past + b"\n" * pad_dump + next_crash
        pad_kernel = 64 * 1024 - len(k) - len(k) // 2
        clipped_kernel = k + b"\n" * pad_kernel + k
        for crashes, kernel, reason in (
            (crash + past + jsonl(record(), record(), joining_record(COREDUMP_PID="4250")), k, "record_limit"),
            (clipped_crash, k, "raw_limit"),
            (crash, clipped_kernel, "kernel_limit"),
            (jsonl(joining_record(total=65)), k, "thread_limit"),
            (jsonl(joining_record(zero=joining_record()["MESSAGE"].splitlines()[-1].replace("#0", "#4") + "\n")),
             k, "ordinal_missing"),
            (jsonl(joining_record(zero=f"#0 {ABSOLUTE_PC} n/a (lib{SECRET}.so + 0x12)\n")), k, "ordinal_missing"),
            (jsonl(joining_record(zero=joining_record()["MESSAGE"].splitlines()[-1] + "\n#0 malformed\n")),
             k, "ordinal_missing"),
            (jsonl(joining_record(_BOOT_ID=None)), k, "malformed"),
            (crash + b'{broken\n', k, "malformed"),
            (crash + jsonl(joining_record(MESSAGE=None)), k, "malformed"),
            (crash, k + b'{broken\n', "malformed"),
            (crash, k + jsonl(kernel_row(None)), "malformed"),
            (crash, k + jsonl(kernel_row(_TRANSPORT=None)), "malformed"),
            *((crash, k + jsonl(kernel_row(line)), "kernel_unsupported_format") for line in NEGATIVE_KERNEL),
        ):
            with self.subTest(reason=reason):
                self.assert_unknown(self.correlated(crashes, kernel), reason)

    def test_global_ambiguity_including_duplicate_kernel_rows(self):
        first = joining_record()
        second = joining_record(
            COREDUMP_PID="4211", MESSAGE=first["MESSAGE"].replace("4204:", "4214:").replace("1234", "1235"),
        )
        other = kernel_row(POSITIVE_KERNEL[0].replace("[4204]", "[4214]").replace("00007f0000001234",
                                                                                  "00007f0000001235"))
        for crashes, kernel in ((jsonl(first, second), jsonl(kernel_row(), other)),
                                (jsonl(first), jsonl(kernel_row(), kernel_row()))):
            with self.subTest(kernel=kernel):
                self.assert_unknown(self.correlated(crashes, kernel), "kernel_ambiguous", complete=True)

    def test_export_budget_keeps_proven_frame_zero_before_peers(self):
        crash = jsonl(record(), joining_record())
        k = jsonl(kernel_row(), kernel_row("irrelevant event"))
        additions = {"source_receipt": {"profile": "webkit", "candidate_source_sha": "c" * 40}}
        expected = self.correlated(crash, k, additions=additions)
        compact = len(json.dumps(expected, separators=(",", ":")).encode("ascii")) + 1
        constrained = self.correlated(crash, k, budget=compact - 190, additions=additions)
        self.assertTrue(constrained["candidate_scan_complete"])
        self.assertIn("export_limit", constrained["omission_reasons"])
        selected = next(row for row in constrained["records"] if row["pid"] == 4201)
        self.assertIsNotNone(selected["fault_attribution"]["fault_thread"])
        self.assertEqual(selected["fault_attribution"]["fault_thread"]["tid"], 4204)
        self.assertEqual(selected["threads"][0]["frames"][0]["ordinal"], 0)
        self.assertEqual(selected["threads"][0]["frames"][0]["offset"], "0x1234")

    def test_explicit_kernel_replay_in_cli_and_never_live_fallback(self):
        path = self.tmp / "kernel-fixture"
        path.write_bytes(jsonl(kernel_row()))
        bootstrap = textwrap.dedent("""
            import runpy, sys
            sys.argv.pop(0)
            main = runpy.run_path(sys.argv[0])["main"]
            def forbid_live(*args, **kwargs):
                raise AssertionError("replay touched live metadata")
            main.__globals__["core_handler"] = forbid_live
            main.__globals__["query"] = forbid_live
            main.__globals__["query_kernel"] = forbid_live
            main.__globals__["installed_identity"] = forbid_live
            raise SystemExit(main())
        """)
        result = self.offline(jsonl(joining_record()), bootstrap=bootstrap, kernel=path)
        self.assertIsNotNone(result["records"][0]["fault_attribution"]["fault_thread"])
        self.assertEqual(result["records"][0]["fault_attribution"]["fault_thread"]["tid"], 4204)
        path.unlink()
        self.assert_unknown(self.offline(jsonl(joining_record()), bootstrap=bootstrap, kernel=path),
                            "kernel_unavailable")
        self.invoke("--kernel-jsonl", str(path), bootstrap=bootstrap, code=2)

    def test_live_kernel_projected_query_results_and_boundary(self):
        coredump = jsonl(joining_record())
        args_file = self.tmp / "args"
        for outcome in ("available", "denied", "missing", "malformed", "overflow"):
            marker = self.tmp / "kernel-process"
            self.fixture(f"""
                import json, os, sys, time
                from pathlib import Path
                if "_TRANSPORT=kernel" not in sys.argv:
                    os.write(1, {coredump!r})
                    if {outcome!r} == "missing":
                        Path(sys.argv[0]).unlink()
                    raise SystemExit(0)
                Path({str(args_file)!r}).write_text(json.dumps(sys.argv[1:]))
                Path({str(marker)!r}).write_text(f'{{os.getpid()}} {{os.getpgrp()}}')
                sys.stderr.write({SECRET!r})
                if {outcome!r} == "denied":
                    raise SystemExit(1)
                if {outcome!r} == "malformed":
                    os.write(1, b"{{broken\\n")
                else:
                    os.write(1, {jsonl(kernel_row())!r})
                if {outcome!r} == "overflow":
                    for _ in range(9):
                        os.write(1, b"X" * 8192)
                    time.sleep(4)
            """, kernel=True)
            with self.subTest(outcome=outcome):
                result = self.invoke()
                self.assertEqual([r["pid"] for r in result["records"]], [4201])
                if outcome == "available":
                    self.assertEqual(result["records"][0]["fault_attribution"]["fault_thread"], {
                        "tid": 4204, "basis": "kernel_tid_and_frame0_pc", "delta_us": 500_000,
                        "frame_zero": {"ordinal": 0, "module": "libWPEWebKit-2.0.so.1", "offset": "0x1234"},
                    })
                    self.assertEqual(json.loads(args_file.read_text()), [
                        "-n", "journalctl", "-b", "--no-pager", "--quiet", "--all",
                        "--since", "@1794837000", "--until", "@1794837062.999999", "_TRANSPORT=kernel",
                        "-o", "json", "--output-fields=MESSAGE,__REALTIME_TIMESTAMP,_BOOT_ID,_TRANSPORT",
                    ])
                else:
                    self.assert_unknown(result, {"overflow": "kernel_limit", "malformed": "malformed"}
                                        .get(outcome, "kernel_unavailable"))
                if outcome != "missing":
                    self.assert_stopped(marker)

    def test_kernel_timeout_reaps_child_and_kills_pipe_holder(self):
        marker = self.tmp / "kernel-timeout"
        survivor = self.tmp / "kernel-descendant-survived"
        self.fixture(f"""
            import os, signal, sys, time
            from pathlib import Path
            if "_TRANSPORT=kernel" not in sys.argv:
                os.write(1, {jsonl(joining_record())!r})
                raise SystemExit(0)
            if os.fork() == 0:
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                time.sleep(2.65)
                Path({str(survivor)!r}).touch()
                os._exit(0)
            Path({str(marker)!r}).write_text(f'{{os.getpid()}} {{os.getpgrp()}}')
            os.write(1, {jsonl(kernel_row())!r})
            time.sleep(4)
        """, kernel=True)
        started = time.monotonic()
        result = self.invoke()
        self.assertLess(time.monotonic() - started, 3.25)
        self.assertEqual([r["pid"] for r in result["records"]], [4201])
        self.assert_unknown(result, "deadline")
        self.assert_stopped(marker)
        time.sleep(max(0, 2.9 - (time.monotonic() - started)))
        self.assertFalse(survivor.exists())

    def test_parent_deadline_uses_prepared_fallback_without_retrying_full_encode(self):
        kernel = self.tmp / "deadline-kernel"
        kernel.write_bytes(jsonl(kernel_row()))
        for stage in ("collect", "encode_export"):
            with self.subTest(stage=stage):
                calls = self.tmp / stage
                bootstrap = textwrap.dedent(f"""
                    import runpy, sys, time
                    from pathlib import Path
                    sys.argv.pop(0)
                    main = runpy.run_path(sys.argv[0])["main"]
                    globals_ = main.__globals__
                    globals_["METADATA_SECONDS"] = 0.30
                    stage = {stage!r}
                    original = globals_[stage]

                    def slow(*args, **kwargs):
                        with Path({str(calls)!r}).open("a") as marker:
                            marker.write("entered\\n")
                        if stage == "encode_export" and args[0]["candidate_scan_complete"]:
                            assert args[0]["records"][0]["fault_attribution"]["fault_thread"]["tid"] == 4204
                        time.sleep(0.65)
                        return original(*args, **kwargs)

                    globals_[stage] = slow
                    raise SystemExit(main())
                """)
                started = time.monotonic()
                result = self.offline(jsonl(joining_record()), kernel=kernel, bootstrap=bootstrap)
                self.assertEqual(calls.read_text(), "entered\n")
                self.assertLess(time.monotonic() - started, 0.80)
                self.assert_unknown(result, "deadline")
                self.assertEqual([r["pid"] for r in result["records"]], [4201] if stage == "encode_export" else [])

    def test_backpressured_output_pipe_cannot_hold_collector_open(self):
        source = self.tmp / "backpressure-crash"
        source.write_bytes(jsonl(record()))
        bootstrap = textwrap.dedent("""
            import runpy, sys
            sys.argv.pop(0)
            main = runpy.run_path(sys.argv[0])["main"]
            main.__globals__["METADATA_SECONDS"] = 0.30
            raise SystemExit(main())
        """)
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            while True:
                try:
                    os.write(write_fd, b"x" * 4096)
                except BlockingIOError:
                    try:
                        # A full atomic-sized write can still leave room
                        # for a short JSON line. Fill the final few bytes.
                        while True:
                            os.write(write_fd, b"x")
                    except BlockingIOError:
                        break
            os.set_blocking(write_fd, True)
            argv = [sys.executable, "-c", bootstrap, str(COLLECTOR), "--since", SINCE, "--until", UNTIL,
                    "--journal-jsonl", str(source)]
            with subprocess.Popen(argv, stdout=write_fd, stderr=subprocess.PIPE, env=self.env) as child:
                try:
                    _stdout, stderr = child.communicate(timeout=0.90)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate(timeout=0.50)
                    self.fail("collector failed to exit while its stdout pipe was full")
                self.assertEqual(child.returncode, 0)
                self.assertEqual(stderr, b"")
        finally:
            os.close(write_fd)
            os.close(read_fd)


class InstalledIdentity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.root = self.tmp / "lib"
        self.root.mkdir()
        self.path = self.root / "libWPEWebKit-2.0.so.1"
        self.collector = runpy.run_path(str(COLLECTOR))

    def test_existing_child_envelope_accepts_private_alias_without_public_leak(self):
        identity = self.collector["installed_identity"]
        alias = "libWPEWebKit-2.0.so.1.10.2"
        envelope = {"sha256": "a"*64, "build_id": "12345678", "_resolved_basename": alias}
        calls = []
        def child(args, limit, read_deadline, cleanup_deadline):
            calls.append((args, limit, read_deadline, cleanup_deadline))
            return "available", json.dumps(envelope).encode(), False, True
        with patch.dict(identity.__globals__, read_child=child):
            receipt, reasons = identity("webkit", [])
        self.assertEqual(receipt, {"module": "libWPEWebKit-2.0.so.1", "sha256": "a"*64,
                                   "build_id": "12345678"})
        self.assertEqual(reasons, set())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], 1024)
        self.assertNotIn(alias, json.dumps(receipt))

    def test_private_identity_strict_envelope_and_shared_child_deadline(self):
        identity = self.collector["installed_identity"]
        valid = {"sha256": "a"*64, "build_id": None,
                 "_resolved_basename": "libWPEWebKit-2.0.so.1.10.2"}
        invalids = [dict(valid, _resolved_basename=value) for value in (
            None, True, SECRET, "/tmp/libWPEWebKit-2.0.so.1", "libWPEWebKit-2.0.so.1\n",
            "libWPEWebKit-2.0.so.1.10.2\x00", "libc.so.6.1", "libWPEWebKit-2.0.so.1.9999",
        )]
        invalids.extend(({k: v for k, v in valid.items() if k != "_resolved_basename"},
                         dict(valid, private=SECRET), dict(valid, sha256="bad"), dict(valid, build_id=True)))
        responses = [("available", json.dumps(item).encode(), False, True, False) for item in invalids]
        exact = json.dumps(valid).encode()
        responses += [("available", exact+b" "*(1024-len(exact)), False, True, True),
                      ("available", json.dumps(valid).encode()+b" "*1024, False, True, False),
                      ("available", json.dumps(valid).encode(), True, True, False),
                      ("available", json.dumps(valid).encode(), False, False, False),
                      ("denied", json.dumps(valid).encode(), False, True, False),
                      ("timeout", json.dumps(valid).encode(), False, True, False),
                      ("available", json.dumps(valid).encode(), False, True, True),
                      ("available", json.dumps(dict(valid, _resolved_basename="libWPEWebKit-2.0.so.1")).encode(), False, True, True)]
        for status, data, cut, reaped, accepted in responses:
            calls = []
            def child(args, limit, read_deadline, cleanup_deadline):
                calls.append((limit, read_deadline, cleanup_deadline))
                return status, data, cut, reaped
            private = {"_resolved_basename": "stale"}
            with self.subTest(status=status, accepted=accepted, data=data[:160]), patch.dict(
                    identity.__globals__, read_child=child), patch.object(time, "monotonic", return_value=100):
                receipt, reasons = identity("webkit", [], deadline=101, private_observation=private)
            self.assertEqual(calls, [(1024, 100.35, 101)])
            if accepted:
                self.assertEqual(receipt, {"module": "libWPEWebKit-2.0.so.1", "sha256": "a"*64, "build_id": None})
                self.assertEqual(private, {"_resolved_basename": json.loads(data)["_resolved_basename"]})
            else:
                self.assertIsNone(receipt)
                self.assertEqual(private, {})
                self.assertIn("identity_missing", reasons)
                if status == "timeout":
                    self.assertIn("deadline", reasons)
                if not reaped:
                    self.assertIn("reap_unconfirmed", reasons)

    def test_resolved_basename_comes_from_existing_validated_elf_read(self):
        read = self.collector["read_elf_identity"]
        data = elf_fixture()
        versioned = self.root / (self.path.name + ".10.2")
        versioned.write_bytes(data)
        self.path.symlink_to(versioned.name)
        with_private = read(self.path, expected_root=self.root, include_resolved_basename=True)
        self.assertEqual(with_private, {"sha256": hashlib.sha256(data).hexdigest(), "build_id": "12345678",
                                        "_resolved_basename": versioned.name})
        self.assertEqual(read(self.path, expected_root=self.root),
                         {"sha256": hashlib.sha256(data).hexdigest(), "build_id": "12345678"})
        versioned.write_bytes(b"invalid")
        self.assertIsNone(read(self.path, expected_root=self.root, include_resolved_basename=True))
        versioned.unlink()
        self.assertIsNone(read(self.path, expected_root=self.root, include_resolved_basename=True))

    def test_build_id_and_hash_with_optional_notes(self):
        for data, expected in (
            (elf_fixture(), "12345678"),
            (elf_fixture((b"\x12\x34\x56\x78",) * 2), "12345678"),
            (elf_fixture(phnum=0), None),
        ):
            self.path.write_bytes(data)
            with self.subTest(expected=expected):
                self.assertEqual(self.collector["read_elf_identity"](self.path, expected_root=self.root),
                                 {"sha256": hashlib.sha256(data).hexdigest(), "build_id": expected})
        versioned = self.root / (self.path.name + ".10.2")
        self.path.rename(versioned)
        self.path.symlink_to(versioned.name)
        self.assertEqual(self.collector["read_elf_identity"](self.path, expected_root=self.root),
                         {"sha256": hashlib.sha256(versioned.read_bytes()).hexdigest(), "build_id": None})

    def test_malformed_or_out_of_policy_elf_and_symlink_escape(self):
        read = self.collector["read_elf_identity"]
        for data in (
            elf_fixture(klass=1), elf_fixture(machine=183),
            elf_fixture(note_offset=4 * 1024 * 1024), elf_fixture(note_offset=63),
            elf_fixture(note_size=1024 * 1024 + 1), elf_fixture(phnum=129),
            elf_fixture(ids=(bytes.fromhex("12345678"), bytes.fromhex("87654321"))),
            elf_fixture()[:-1],
        ):
            with self.subTest(data=data[:24]):
                self.path.write_bytes(data)
                self.assertIsNone(read(self.path, expected_root=self.root))
        with self.path.open("wb") as f:
            f.write(elf_fixture())
            f.truncate(256 * 1024 * 1024 + 1)
        self.assertIsNone(read(self.path, expected_root=self.root))
        outside = self.tmp / self.path.name
        outside.write_bytes(elf_fixture())
        self.path.unlink()
        self.path.symlink_to(outside)
        self.assertIsNone(read(self.path, expected_root=self.root))

    def test_elf_note_budget_with_in_file_payload_at_and_over_limit(self):
        read = self.collector["read_elf_identity"]
        for size in (1024 * 1024, 1024 * 1024 + 4):
            data = elf_fixture(padded_note_size=size)
            self.path.write_bytes(data)
            self.assertEqual(self.path.stat().st_size, 120 + size)
            with self.subTest(note_size=size):
                receipt = read(self.path, expected_root=self.root)
                if size == 1024 * 1024:
                    self.assertEqual(receipt, {"sha256": hashlib.sha256(data).hexdigest(),
                                               "build_id": "12345678"})
                else:
                    self.assertIsNone(receipt)

    def test_installed_file_changed_during_streaming_is_rejected(self):
        read = self.collector["read_elf_identity"]
        for change in ("inode", "size", "mtime"):
            self.path.write_bytes(elf_fixture())
            original = self.path.stat()
            real_hash = hashlib.sha256

            class MutatingHash:
                def __init__(test_self):
                    test_self.real = real_hash()

                def update(test_self, chunk):
                    test_self.real.update(chunk)
                    if change == "inode":
                        new = self.path.with_suffix(".replacement")
                        new.write_bytes(elf_fixture())
                        os.replace(new, self.path)
                    elif change == "size":
                        with self.path.open("ab") as file:
                            file.write(b"more")
                    else:
                        os.utime(self.path, ns=(original.st_atime_ns, original.st_mtime_ns + 20_000_000))

                def hexdigest(test_self):
                    return test_self.real.hexdigest()

            with self.subTest(change=change), patch.object(hashlib, "sha256", MutatingHash):
                self.assertIsNone(read(self.path, expected_root=self.root, include_resolved_basename=True))

    def test_installed_child_stays_separate_from_crash_identity(self):
        self.path.write_bytes(elf_fixture())
        collect = self.collector["collect"]
        identity = self.collector["installed_identity"]
        identity.__globals__["WPE_LIBRARY"] = self.path
        indexed = self.collector["summary"]("available")
        collect(indexed, jsonl(record(), record(COREDUMP_PACKAGE_JSON=json.dumps({
            self.path.name: {"buildId": "12345678"},
        })), record(COREDUMP_PACKAGE_JSON=json.dumps({self.path.name: {"buildId": "deadbeef"}}))),
                False, int(SINCE), int(UNTIL))
        private = {}
        receipt, reasons = identity("webkit", indexed["records"], private_observation=private)
        self.assertEqual(private, {"_resolved_basename": self.path.name})
        self.assertEqual(receipt, {"sha256": hashlib.sha256(elf_fixture()).hexdigest(),
                                   "build_id": "12345678", "module": self.path.name})
        self.assertEqual(reasons, set())
        self.assertEqual([r["module_identity"] for r in indexed["records"]],
                         [{}, {self.path.name: "12345678"}, {self.path.name: "deadbeef"}])

    def test_gpu_installed_child_requires_exactly_one_eligible_crash(self):
        identity = self.collector["installed_identity"]
        first = self.root / "test_parity-0123456789abcdef"
        second = self.root / "test_parity-0123456789abcdee"
        for path in (first, second):
            path.write_bytes(elf_fixture())
        identity.__globals__["PARITY_DEPS"] = self.root
        row = {"_parity_exe": first}
        self.assertEqual(identity("gpu-parity", [row])[0], {
            "sha256": hashlib.sha256(elf_fixture()).hexdigest(), "build_id": "12345678", "module": first.name,
        })
        for rows in ([], [row, row], [row, {"_parity_exe": second}]):
            self.assertIsNone(identity("gpu-parity", rows)[0])


class SourceReceipt(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.collector = runpy.run_path(str(COLLECTOR))
        self.produce = self.collector["source_receipt"]
        self.state = self.produce.__globals__
        self.state["REPOSITORY_ROOT"] = self.tmp
        self.lock = self.tmp / "implementation/marketing/package-lock.json"
        self.lock.parent.mkdir(parents=True)
        self.lock.write_bytes(b"abc")
        cargo = self.tmp / "implementation/desktop/Cargo.lock"
        cargo.parent.mkdir(parents=True)
        cargo.write_bytes(b"abc")
        (self.tmp / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.98.0"\n')
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.witness = self.tmp / "calls"
        self.command("git", "printf '%s\\n' " + "a" * 40 + " " + "b" * 40)
        self.command("systemd", "printf '%s\\n' 'systemd 259 (private build)' " + SECRET)
        self.environ = {"PATH": str(self.bin), "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "2"}

    def command(self, name, body):
        expected = ["-C", str(self.tmp), "rev-parse", "HEAD", "HEAD^{tree}"] if name == "git" else ["--version"]
        path = self.bin / name
        checks = "\n".join(f'[ "${i}" = {shlex.quote(arg)} ] || exit 97' for i, arg in enumerate(expected, 1))
        path.write_text(f"#!/bin/sh\n[ \"$#\" = {len(expected)} ] || exit 97\n" + checks + "\n"
                        + f"printf '%s\\n' {name} >> {shlex.quote(str(self.witness))}\n" + body + "\n")
        path.write_text(path.read_text().replace("#!/bin/sh\n", '#!/bin/sh\n[ "$FIXTURE_PREPARE" != 1 ] || exit 0\n', 1))
        path.chmod(0o700)
        # Fresh local fixture executables have taken >0.5s to start here; the
        # cause is unknown. Prepare them before testing the unchanged production
        # half-second budget; this is fixture preparation, never a probe retry.
        subprocess.run([str(path), *expected], env={"FIXTURE_PREPARE": "1"}, capture_output=True, timeout=2)
        self.witness.write_text("")

    def receipt(self, profile="webkit", candidate="c" * 40):
        with patch.dict(os.environ, self.environ, clear=True), patch.object(os, "uname", return_value=type("U", (), {"release": "6.8.0-fixture"})()):
            receipt = self.produce(profile, candidate, deadline=time.monotonic() + 2)
        result = self.collector["summary"]("empty")
        result["source_receipt"] = receipt
        raw = self.collector["encode_export"](result)
        self.assertNotIn(SECRET, raw)
        self.assertNotIn(str(self.tmp), raw)
        return json.loads(raw).get("source_receipt", {})

    def test_source_receipt_actual_checkout_is_distinct_from_candidate(self):
        result = self.receipt()
        self.assertEqual(result.get("checkout_sha"), "a" * 40)
        self.assertEqual(result.get("tree_sha"), "b" * 40)
        self.assertEqual(result.get("candidate_source_sha"), "c" * 40)
        self.assertEqual(result.get("run_id"), "12345")
        self.assertEqual(result.get("run_attempt"), "2")
        self.assertEqual(result.get("kernel_release"), "6.8.0-fixture")
        self.assertEqual(result.get("systemd_version"), "259")
        self.assertEqual(result.get("profile"), "webkit")
        self.assertEqual(result.get("job"), "marketing")
        self.assertEqual(result.get("playwright_version"), "1.65.2")
        self.assertEqual(result.get("webkit_revision"), "2388")
        self.assertEqual(result.get("lock_sha256"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertTrue(result.get("complete"))
        self.assertEqual(self.witness.read_text().splitlines(), ["git", "systemd"])

    def test_source_receipt_gpu_uses_fixed_channel_and_lock(self):
        result = self.receipt("gpu-parity")
        self.assertEqual(result.get("job"), "rust")
        self.assertEqual(result.get("rust_channel"), "1.98.0")
        self.assertEqual(result.get("lock_sha256"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertNotIn("playwright_version", result)
        self.assertTrue(result.get("complete"))

    def test_source_receipt_unavailable_and_hostile_values_are_unknown(self):
        self.command("git", "printf '%s\\n' " + SECRET)
        self.command("systemd", "printf '%s\\n' 'systemd " + SECRET + "'")
        self.environ.update(GITHUB_RUN_ID=SECRET, GITHUB_RUN_ATTEMPT="9" * 21)
        result = self.receipt(candidate=SECRET)
        self.assertFalse(result.get("complete", True))
        for field in ("checkout_sha", "tree_sha", "candidate_source_sha", "systemd_version", "run_id", "run_attempt"):
            self.assertIn(field, result)
            self.assertIsNone(result[field])
        (self.bin / "git").unlink()
        result = self.receipt()
        self.assertIsNone(result["checkout_sha"])
        self.assertIsNone(result["systemd_version"])
        self.assertFalse(result["complete"])


    def test_nonzero_output_cannot_reset_the_shared_probe_byte_budget(self):
        self.command("git", "printf '%04096d' 0; exit 1")
        result = self.receipt()
        self.assertIsNone(result.get("systemd_version"))
        self.assertEqual(self.witness.read_text().splitlines(), ["git"])
        self.assertFalse(result["complete"])

    def test_shared_probe_deadline_and_output_overflow_are_bounded(self):
        # A second child never receives a fresh half-second or fresh 4 KiB.
        self.command("git", "/bin/sleep 0.30; printf '%s\\n' " + "a" * 40 + " " + "b" * 40)
        marker = self.tmp / "timed-out-child"
        self.command("systemd", f"printf '%s\\n' \"$$\" > {shlex.quote(str(marker))}; /bin/sleep 0.30; printf '%s\\n' 'systemd 259'")
        start = time.monotonic()
        result = self.receipt()
        self.assertLess(time.monotonic() - start, 0.85)
        self.assertIsNone(result["systemd_version"])
        self.assertFalse(result["complete"])
        self.assertEqual(self.witness.read_text().splitlines(), ["git", "systemd"])
        with self.assertRaises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)
        self.command("git", "printf '%04080d' 0")
        self.command("systemd", "printf 'systemd 259\\n1234'")
        result = self.receipt()
        self.assertEqual(result["systemd_version"], "259")
        self.assertFalse(result["complete"])
        self.command("systemd", "printf '%s' 'systemd 259 '; printf '%040d' 0")
        result = self.receipt()
        self.assertIsNone(result["checkout_sha"])
        self.assertIsNone(result["systemd_version"])
        self.assertFalse(result["complete"])
        self.assertEqual(self.witness.read_text().splitlines(), ["git", "systemd"])
        self.command("git", "printf '%04097d' 0")
        result = self.receipt()
        self.assertEqual(self.witness.read_text().splitlines(), ["git"])
        self.assertFalse(result["complete"])

    def test_source_fixed_files_reject_size_nonregular_escape_and_mutation(self):
        self.lock.write_bytes(b"x" * (1024 * 1024))
        self.assertEqual(self.receipt()["lock_sha256"], hashlib.sha256(b"x" * (1024 * 1024)).hexdigest())
        self.lock.write_bytes(b"x" * (1024 * 1024 + 1))
        self.assertIsNone(self.receipt()["lock_sha256"])
        self.lock.unlink()
        os.mkfifo(self.lock)
        self.assertIsNone(self.receipt()["lock_sha256"])
        self.lock.unlink()
        outside = self.tmp / "outside"
        outside.write_bytes(b"abc")
        self.lock.symlink_to(outside)
        self.assertIsNone(self.receipt()["lock_sha256"])
        self.lock.unlink()
        self.lock.write_bytes(b"abc")
        original = os.fstat
        calls = 0
        def changed(fd):
            nonlocal calls
            result = original(fd)
            calls += 1
            if calls == 1:
                self.lock.write_bytes(b"xyz")
            return result
        with patch.object(os, "fstat", side_effect=changed):
            self.assertIsNone(self.receipt()["lock_sha256"])
        toolchain = self.tmp / "rust-toolchain.toml"
        for content in (b"x" * 4097, b'[toolchain]\nchannel="stable"', b'[toolchain]\nchannel="1.2.3"\nchannel="9.8.7"'):
            toolchain.write_bytes(content)
            self.assertIsNone(self.receipt("gpu-parity")["rust_channel"])

    def test_source_export_revalidates_and_does_not_change_kernel_ownership(self):
        result = self.collector["summary"]("available")
        self.collector["collect"](result, jsonl(joining_record()), False, int(SINCE), int(UNTIL))
        self.collector["attach_kernel"](result, "available", jsonl(kernel_row()), False, True)
        result["source_receipt"] = {
            "profile": "webkit", "checkout_sha": "a" * 40, "tree_sha": "b" * 40,
            "candidate_source_sha": "c" * 40, "run_id": "12345", "run_attempt": "2",
            "kernel_release": "6.8.0-fixture", "systemd_version": "259", "lock_sha256": "f" * 64,
            "playwright_version": "1.61.0", "webkit_revision": "2311", "complete": True,
        }
        safe = json.loads(self.collector["encode_export"](result))
        self.assertIsNone(safe["source_receipt"]["playwright_version"])
        self.assertIsNone(safe["source_receipt"]["webkit_revision"])
        self.assertFalse(safe["source_receipt"]["complete"])

        result["source_receipt"] = {"profile": "webkit", "checkout_sha": SECRET, "arbitrary": SECRET,
                                    "kernel_release": "x/" + SECRET, "job": SECRET, "complete": True}
        result["kernel_rejection_stage"] = SECRET
        safe = json.loads(self.collector["encode_export"](result))
        self.assertNotIn(SECRET, json.dumps(safe))
        self.assertFalse(safe["source_receipt"]["complete"])
        self.assertTrue(safe["candidate_scan_complete"])
        self.assertEqual(safe["records"][0]["fault_attribution"]["fault_thread"]["tid"], 4204)

    def test_main_receipt_integration_and_offline_invalid_window_no_host(self):
        main = self.collector["main"]
        state = main.__globals__
        outputs = []
        state["write_export"] = lambda encoded, deadline: outputs.append(json.loads(encoded))
        state["core_handler"] = lambda: "not_checked"
        state["query"] = lambda *args: ("available", b"", False, True)
        state["query_kernel"] = lambda *args: ("available", b"", False, True)
        state["installed_identity"] = lambda *args, **kwargs: (None, set())
        args = [str(COLLECTOR), "--since", SINCE, "--until", UNTIL, "--candidate-source-sha", "c" * 40]
        with patch.dict(os.environ, self.environ, clear=True), patch.object(os, "uname", return_value=type("U", (), {"release": "6.8.0-fixture"})()), patch.object(sys, "argv", args):
            self.assertEqual(main(), 0)
        self.assertEqual(outputs[-1]["source_receipt"]["checkout_sha"], "a" * 40)
        def forbidden(*args, **kwargs):
            self.fail("offline/invalid invocation reached a host probe")
        for name in ("source_receipt", "core_handler", "query", "query_kernel", "installed_identity"):
            state[name] = forbidden
        replay = self.tmp / "replay"
        replay.write_bytes(b"")
        for extra, since, expected in ((["--journal-jsonl", str(replay)], SINCE, 0), ([], "", 2)):
            with patch.object(sys, "argv", [str(COLLECTOR), "--since", since, "--until", UNTIL, *extra]):
                self.assertEqual(main(), expected)
                self.assertNotIn("source_receipt", outputs[-1])


    def test_parent_watchdog_discards_partial_receipt_without_losing_safe_fallback(self):
        main = self.collector["main"]
        state = main.__globals__
        outputs = []
        state["METADATA_SECONDS"] = 0.20
        state["write_export"] = lambda encoded, deadline: outputs.append(json.loads(encoded))
        state["core_handler"] = lambda: "not_checked"
        state["query"] = lambda *args: ("available", jsonl(joining_record()), False, True)
        state["query_kernel"] = lambda *args: ("available", jsonl(kernel_row()), False, True)
        def slow_receipt(*args, **kwargs):
            time.sleep(0.40)
            return {"profile": "webkit", "checkout_sha": "a" * 40}
        state["source_receipt"] = slow_receipt
        args = [str(COLLECTOR), "--since", SINCE, "--until", UNTIL]
        start = time.monotonic()
        with patch.object(sys, "argv", args):
            self.assertEqual(main(), 0)
        self.assertLess(time.monotonic() - start, 0.40)
        self.assertNotIn("source_receipt", outputs[-1])
        self.assertNotIn("kernel_rejection_stage", outputs[-1])
        self.assertIn("deadline", outputs[-1]["omission_reasons"])
        self.assertFalse(outputs[-1]["candidate_scan_complete"])
        self.assertIsNone(outputs[-1]["records"][0]["fault_attribution"]["fault_thread"])


class WorkflowCommands(unittest.TestCase):
    def step(self, name):
        # Only named six-space step blocks and their literal run forms are admitted.
        text = (COLLECTOR.parents[3] / ".github/workflows/ci.yml").read_text()
        marker = "      - name: " + name + "\n"
        self.assertEqual(text.count(marker), 1)
        block = text.split(marker, 1)[1]
        block = re.split(r"^      - |^[^ #]", block, maxsplit=1, flags=re.M)[0]
        lines = block.splitlines()
        run = next(i for i, line in enumerate(lines) if line.startswith("        run: "))
        value = lines[run].removeprefix("        run: ")
        if value == "|":
            selected = []
            for line in lines[run + 1:]:
                if line and not line.startswith("          "):
                    break
                selected.append(line[10:])
            value = "\n".join(selected)
        self.assertNotEqual(value, ">-")
        return block, value

    def test_actual_workflow_shells_preserve_gate_exits_and_diagnostic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            calls, output = tmp / "calls", tmp / "output"
            env = {"PATH": str(tmp), "GITHUB_OUTPUT": str(output), "CALLS": str(calls),
                   "CANDIDATE_SOURCE_SHA": "c" * 40, "WEBKIT_SWEEP_STARTED_AT": SINCE,
                   "GPU_PARITY_STARTED_AT": SINCE}
            fake = """#!/bin/sh
case "$0" in
  */date) [ "$#" = 1 ] && [ "$1" = +%s ] || exit 97
    [ "$DATE_FAIL" != 1 ] || exit 9
    printf '%s\n' 1794837000 ;;
  */cargo) [ "$*" = 'test --workspace --no-fail-fast' ] || exit 97
    printf '%s\n' cargo >> "$CALLS"
    exit "$GATE_STATUS" ;;
  */python3)
    if [ "$1" = scripts/responsive_sweep.py ]; then
      [ "$*" = 'scripts/responsive_sweep.py --engine webkit' ] || exit 97
      printf '%s\n' sweep >> "$CALLS"
      exit "$GATE_STATUS"
    fi
    [ "$#" = 9 ] || exit 97
    case "$1:$3" in
      ../marketing/scripts/webkit_crash_journal.py:gpu-parity|scripts/webkit_crash_journal.py:webkit) ;;
      *) exit 97 ;;
    esac
    [ "$2" = --profile ] && [ "$4" = --candidate-source-sha ] && [ "$5" = "$CANDIDATE_SOURCE_SHA" ] || exit 97
    [ "$6" = --since ] && [ "$7" = 1794837000 ] && [ "$8" = --until ] && [ "$9" = 1794837000 ] || exit 97
    printf '%s\n' collector >> "$CALLS"
    exit 19 ;;
  *) exit 97 ;;
esac
"""
            for name in ("date", "cargo", "python3"):
                path = tmp / name
                path.write_text(fake)
                path.chmod(0o700)
            for gate, diagnostic, witness, statuses in (
                (
                    "Test (workspace, incl. GPU parity where an adapter exists)",
                    "Collect existing GPU parity crash summaries",
                    "cargo",
                    (0, 101, 2),
                ),
                (
                    "Responsive sweep (WebKit)",
                    "Collect existing WebKit crash summaries",
                    "sweep",
                    (0, 101, 2, 1, 3),
                ),
            ):
                block, command = self.step(gate)
                # This exact expansion is Linux-only; Windows retains an empty
                # prelude and its default shell. Never interpret arbitrary YAML.
                expression = re.compile(r"\$\{\{ runner.os == 'Linux' && '(.*)' \|\| '' \}\}")
                command = expression.sub(lambda match: match[1].replace("''", "'"), command)
                self.assertNotIn("${{", command)
                self.assertNotIn("shell:", block)
                self.assertIn("if: ${{ !cancelled() }}", block)
                self.assertNotIn("continue-on-error:", block)
                for code in statuses:
                    output.write_text("")
                    calls.write_text("")
                    run = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", command],
                                         env={**env, "GATE_STATUS": str(code)}, capture_output=True, timeout=2)
                    self.assertEqual(run.returncode, code, run.stderr)
                    self.assertEqual(calls.read_text().splitlines(), [witness])
                    self.assertEqual(output.read_text(), "started_at=1794837000\n")
                    collector_block, collector = self.step(diagnostic)
                    self.assertIn("continue-on-error: true", collector_block)
                    run = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", collector],
                                         env=env, capture_output=True, timeout=2)
                    self.assertEqual(run.returncode, 19, run.stderr)
                    self.assertEqual(calls.read_text().splitlines(), [witness, "collector"])
                    # Actions conclusion mapping is modeled, not hosted proof:
                    # a separately continued diagnostic leaves the original code.
                    effective = code if "continue-on-error: true" in collector_block else run.returncode
                    self.assertEqual(effective, code)
                    for failure in ("date", "output"):
                        output.write_text("")
                        bad = {**env, "GATE_STATUS": str(code), "DATE_FAIL": "1" if failure == "date" else "0"}
                        if failure == "output":
                            bad["GITHUB_OUTPUT"] = str(tmp)
                        run = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", command],
                                             env=bad, capture_output=True, timeout=2)
                        self.assertEqual(run.returncode, code)
                        self.assertEqual(output.read_text(), "")
                step_id = "workspace_tests" if witness == "cargo" else "responsive_webkit"
                expected = "!cancelled() && " + ("runner.os == 'Linux' && " if witness == "cargo" else "")
                expected += f"(steps.{step_id}.outcome == 'success' || steps.{step_id}.outcome == 'failure')"
                self.assertIn("if: ${{ " + expected + " }}", collector_block)
                if witness == "cargo":
                    self.assertIn("SELAHCUE_GPU_PARITY_DIAGNOSTICS: ${{ runner.os == 'Linux' && '1' || '' }}", block)


def _token():
    return f"::error::{SECRET}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
