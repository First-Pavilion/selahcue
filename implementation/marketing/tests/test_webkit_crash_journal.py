"""Offline CLI and subprocess boundary controls; no tests read a real journal."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest


COLLECTOR = Path(__file__).resolve().parents[1] / "scripts" / "webkit_crash_journal.py"
BUNDLE_BIN = "/home/runner/.cache/ms-playwright/webkit-2311/minibrowser-wpe/bin"
SINCE = "1794837000"
UNTIL = "1794837060"
CRASH = "1794837031000000"
SECRET = "SyntheticPrivateToken"
ABSOLUTE_PC = "0x00007fbe01234567"


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

    def fixture(self, body):
        sudo = self.tmp / "sudo"
        sudo.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body).lstrip())
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
                runpy.run_path(sys.argv[0], run_name="__main__")
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

    def offline(self, data, **kwargs):
        source = self.tmp / f"{SECRET}.jsonl"
        source.write_bytes(data)
        return self.invoke("--journal-jsonl", str(source), **kwargs)

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
                runpy.run_path(sys.argv[0], run_name="__main__")
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


def _token():
    return f"::error::{SECRET}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
