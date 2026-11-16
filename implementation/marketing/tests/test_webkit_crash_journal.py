"""Offline CLI and subprocess boundary controls; no tests read a real journal."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch


COLLECTOR = Path(__file__).resolve().parents[1] / "scripts" / "webkit_crash_journal.py"
BUNDLE_BIN = "/home/runner/.cache/ms-playwright/webkit-2311/minibrowser-wpe/bin"
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
            row(15, f"{BUNDLE_BIN.replace('2311', '2312')}/WPEWebProcess"),
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
        export = collector["export"]
        budget = len(json.dumps(result, separators=(",", ":")).encode("ascii")) + 1 - 100
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

    def correlated(self, crashes, kernel, *, cut=False, budget=None):
        result = self.collector["summary"]("available")
        self.collector["collect"](result, crashes, cut, int(SINCE), int(UNTIL))
        records, complete, reasons = self.collector["correlate_kernel"](
            result["records"], kernel, result["candidate_scan_complete"],
        )
        result.update(records=records, candidate_scan_complete=complete,
                      omission_reasons=sorted({*result["omission_reasons"], *reasons}))
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
        expected = self.correlated(crash, k)
        compact = len(json.dumps(expected, separators=(",", ":")).encode("ascii")) + 1
        constrained = self.correlated(crash, k, budget=compact - 190)
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
                self.assertIsNone(read(self.path, expected_root=self.root))

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
        receipt, reasons = identity("webkit", indexed["records"])
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


def _token():
    return f"::error::{SECRET}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
