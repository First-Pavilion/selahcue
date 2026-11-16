"""Offline CLI and subprocess boundary controls; no tests read a real journal."""
import json
import os
from pathlib import Path
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

    def invoke(self, *extra, since=SINCE, until=UNTIL, code=0):
        # Make RED about missing CLI behavior, without starting a broken interpreter command.
        self.assertTrue(COLLECTOR.is_file(), "missing WebKit crash journal CLI")
        result = subprocess.run(
            [sys.executable, str(COLLECTOR), "--since", since, "--until", until, *extra],
            env=self.env, capture_output=True, timeout=5, check=False,
        )
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.returncode, code)
        self.assertEqual(result.stdout.count(b"\n"), 1)
        self.assertLessEqual(len(result.stdout), 8 * 1024)
        self.assertNotIn(SECRET.encode(), result.stdout)
        self.assertNotIn(ABSOLUTE_PC.encode(), result.stdout)
        self.assertNotIn(b"/home/runner", result.stdout)
        return json.loads(result.stdout)

    def offline(self, data, **kwargs):
        source = self.tmp / f"{SECRET}.jsonl"
        source.write_bytes(data)
        return self.invoke("--journal-jsonl", str(source), **kwargs)

    def test_sigabrt_metadata_and_only_safe_stack_evidence(self):
        result = self.offline(jsonl(record()))
        self.assertEqual(result, {
            "availability": "available", "handler": "not_checked",
            "partial": True, "truncated": False, "rejected_records": 0,
            "records": [{
                "pid": 27625, "timestamp_us": 1794837031000000, "signal": "SIGABRT",
                "role": "web_process", "partial": True,
                "frames": [
                    {"module": "libc.so.6", "offset": "0x97259", "symbol": "malloc_printerr"},
                    {"module": "libWPEWebKit-2.0.so.1", "offset": "0x40ab"},
                ],
            }],
        })

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
        self.assertEqual([(r["partial"], r["frames"]) for r in result["records"]],
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
                f"#6  {ABSOLUTE_PC} malloc_printerr (libc.so.6 + 0x00007fbe01234567)\n"
                f"#7  {ABSOLUTE_PC} abort (libc.so.6 + 0x15)\n"
            ),
        )))
        self.assertTrue(result["partial"])
        self.assertEqual(result["records"][0]["frames"], [
            {"module": "libc.so.6", "offset": "0x10"},
            {"module": "libc.so.6", "offset": "0x11"},
            {"module": "libc.so.6", "offset": "0x12"},
            {"module": "libc.so.6", "offset": "0x15", "symbol": "abort"},
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
        self.assertEqual([len(r["frames"]) for r in result["records"]], [12, 12, 12])

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

    def test_live_query_uses_fixed_read_only_argv_and_real_output_boundary(self):
        receipt = self.tmp / "argv"
        self.fixture(f"""
            import json, os, sys
            from pathlib import Path
            Path({str(receipt)!r}).write_text(json.dumps([sys.argv[1:], os.getpid(), os.getpgrp()]))
            sys.stderr.write({SECRET!r})
            sys.stdout.buffer.write({jsonl(record())!r})
        """)
        result = self.invoke()
        self.assertEqual([r["pid"] for r in result["records"]], [27625])
        self.assertIn(result["handler"], ("systemd_coredump", "other_pipe", "file", "unavailable"))
        args, pid, group = json.loads(receipt.read_text())
        self.assertEqual(pid, group)
        self.assertNotEqual(group, os.getpgrp())
        self.assertEqual(args, [
            "-n", "journalctl", "-b", "--no-pager", "--quiet", "--all",
            "--since", "@1794837000", "--until", "@1794837060.999999",
            "MESSAGE_ID=fc2e22bc6ee647b6b90729ab34a250b1", "-o", "json",
            "--output-fields=COREDUMP_TIMESTAMP,COREDUMP_PID,COREDUMP_SIGNAL_NAME,"
            "COREDUMP_EXE,COREDUMP_COMM,MESSAGE",
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
                time.sleep(4.75)
                Path({str(survivor)!r}).touch()
                os._exit(0)
            Path({str(marker)!r}).write_text(f'{{os.getpid()}} {{os.getpgrp()}}')
            time.sleep(4.85)
        """)
        started = time.monotonic()
        result = self.invoke()
        self.assertEqual(result["availability"], "timeout")
        self.assertTrue(result["partial"])
        self.assert_stopped(marker)
        time.sleep(max(0, 4.95 - (time.monotonic() - started)))
        self.assertFalse(survivor.exists())


def _token():
    return f"::error::{SECRET}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
