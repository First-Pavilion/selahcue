"""Read existing systemd crash summaries for the pinned hosted WebKit sweep.

--since and --until are inclusive UTC epoch seconds. --journal-jsonl replays a
regular file without consulting the host journal or core handler. A diagnostic
result (including unavailable, timeout, or malformed) exits 0; an invalid
window or invocation emits the same safe schema and exits 2.
"""
import argparse
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import time


RAW_LIMIT = 256 * 1024
EXPORT_LIMIT = 8 * 1024
RECORD_LIMIT = 3
FRAME_LIMIT = 12
# Reserve time within five seconds for signaling the sudo supervisor and reaping.
QUERY_SECONDS = 4
TERMINATION_GRACE = 0.15
REAP_SECONDS = 0.5
MESSAGE_ID = "fc2e22bc6ee647b6b90729ab34a250b1"
FIELDS = "COREDUMP_TIMESTAMP,COREDUMP_PID,COREDUMP_SIGNAL_NAME,COREDUMP_EXE,COREDUMP_COMM,MESSAGE"

# The hosted log fixes the cache root and revision. The pinned Playwright
# registry identifies the WPE bin directory; the WebKit WPE build names its
# helpers. pw_run.sh and the MiniBrowser shell wrapper are not ELF crash roles.
BUNDLE = "/home/runner/.cache/ms-playwright/webkit-2311/minibrowser-wpe"
ROLES = {
    f"{BUNDLE}/bin/MiniBrowser": "browser",
    f"{BUNDLE}/bin/WPEWebProcess": "web_process",
    f"{BUNDLE}/bin/WPENetworkProcess": "network_process",
    f"{BUNDLE}/bin/WPEGPUProcess": "gpu_process",
}
SIGNALS = {
    "SIGABRT", "SIGBUS", "SIGFPE", "SIGILL", "SIGQUIT", "SIGSEGV",
    "SIGSYS", "SIGTRAP", "SIGXCPU", "SIGXFSZ",
}
MODULE_SYMBOLS = {
    "libc.so.6": {
        "__GI_abort", "__GI_raise", "__GI___libc_free", "__libc_free", "__libc_malloc",
        "__pthread_kill", "__pthread_kill_implementation", "__pthread_kill_internal",
        "_int_free", "_int_free_chunk", "_int_free_merge_chunk",
        "_int_free_create_chunk", "_int_malloc", "abort", "free", "malloc",
        "malloc_printerr", "pthread_kill", "raise",
    },
    "libsoup-3.0.so.0": {"soup_session_abort", "soup_session_send", "soup_session_send_async"},
    "libglib-2.0.so.0": {"g_free", "g_malloc", "g_malloc0", "g_realloc"},
    "libgobject-2.0.so.0": {"g_object_ref", "g_object_unref"},
    "libWPEWebKit-2.0.so.1": set(),
    "libjavascriptcoregtk-4.1.so.0": set(),
    "libgstreamer-1.0.so.0": set(),
    "libgstbase-1.0.so.0": set(),
    "libstdc++.so.6": set(),
    "libgcc_s.so.1": set(),
    "libpthread.so.0": set(),
    "ld-linux-x86-64.so.2": set(),
    **{exe.rsplit("/", 1)[1]: set() for exe in ROLES},
}
MODULE_DIRS = {"/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu",
               f"{BUNDLE}/lib", f"{BUNDLE}/sys/lib"}
VERSIONED_MODULE = re.compile(r"(.{1,48}\.so\.[0-9]{1,2})(?:\.[0-9]{1,3}){1,2}")
THREAD = re.compile(r"Stack trace of thread [1-9][0-9]{0,9}:")
FRAME = re.compile(
    r"#[0-9]{1,3} +0x([0-9a-f]{1,16}) ([^\r\n]*) "
    r"\(([^ ()\r\n]+) \+ 0x([0-9a-f]{1,8})\)"
)


class PrivateParser(argparse.ArgumentParser):
    def error(self, _message):
        raise ValueError


def number(value, digits):
    if not isinstance(value, str) or not re.fullmatch(rf"[1-9][0-9]{{0,{digits - 1}}}", value):
        raise ValueError
    return int(value)


def summary(availability="unavailable", handler="not_checked"):
    return {
        "availability": availability, "handler": handler,
        "partial": availability != "empty", "truncated": False,
        "rejected_records": 0, "records": [],
    }


def core_handler():
    try:
        with open("/proc/sys/kernel/core_pattern", "rb") as source:
            pattern = source.read(256).lstrip()
    except OSError:
        return "unavailable"
    if not pattern.startswith(b"|"):
        return "file" if pattern.strip() else "unavailable"
    command = pattern[1:].split(None, 1)
    if command and command[0] in (
        b"/usr/lib/systemd/systemd-coredump", b"/lib/systemd/systemd-coredump",
    ):
        return "systemd_coredump"
    return "other_pipe"


def replay(path):
    # Opening a FIFO with ordinary read flags would block before fstat.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    # Keep the one-byte overflow probe from filling a read-ahead buffer.
    with os.fdopen(fd, "rb", buffering=0) as source:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return "unavailable", b"", False
        data = bytearray()
        while len(data) < RAW_LIMIT:
            chunk = source.read(RAW_LIMIT - len(data))
            if not chunk:
                return "available", data, False
            data.extend(chunk)
        return "available", data, bool(source.read(1))


def stop_owned_group(child):
    # Signal before waiting, so the PID remains reserved until its group has
    # been signaled. TERM lets sudo forward termination to its elevated child.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        except PermissionError:
            break
        if sig == signal.SIGTERM:
            time.sleep(TERMINATION_GRACE)
    try:
        child.wait(timeout=REAP_SECONDS)
    except subprocess.TimeoutExpired:
        # Keep export bounded even if the OS cannot reap a stuck process yet.
        pass


def query(since, until):
    # --all retains MESSAGE fields larger than journalctl's default JSON
    # threshold (4096 bytes). The six-field projection and our own read cap
    # still apply. Journalctl also adds its unavoidable JSON bookkeeping.
    args = [
        "sudo", "-n", "journalctl", "-b", "--no-pager", "--quiet", "--all",
        "--since", f"@{since}", "--until", f"@{until}.999999",
        f"MESSAGE_ID={MESSAGE_ID}", "-o", "json", f"--output-fields={FIELDS}",
    ]
    deadline = time.monotonic() + QUERY_SECONDS
    child = subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    data = bytearray()
    finished = False
    try:
        fd = child.stdout.fileno()
        os.set_blocking(fd, False)
        with selectors.DefaultSelector() as watcher:
            watcher.register(fd, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not watcher.select(remaining):
                    return "timeout", data, True
                # The final one-byte probe detects overflow; it is never
                # retained or parsed as part of the capped capture.
                room = RAW_LIMIT - len(data)
                try:
                    chunk = os.read(fd, min(8192, room) if room else 1)
                except BlockingIOError:
                    continue
                if not chunk:
                    break
                if not room:
                    return "available", data, True
                data.extend(chunk)
        try:
            status = child.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            return "timeout", data, True
        finished = True
        return ("available", data, False) if status == 0 else ("unavailable", b"", False)
    finally:
        child.stdout.close()
        if not finished:
            stop_owned_group(child)


def unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError
    return fields


def invalid_constant(_value):
    raise ValueError


def approved_module(module):
    directory, slash, name = module.rpartition("/")
    if module in ROLES:
        return name
    if slash and directory not in MODULE_DIRS:
        return None
    if name not in MODULE_SYMBOLS:
        versioned = VERSIONED_MODULE.fullmatch(name)
        name = versioned[1] if versioned else None
    return name if name in MODULE_SYMBOLS else None


def stack(message):
    frames = []
    partial = truncated = False
    in_stack = False
    if not isinstance(message, str):
        return frames, True, False
    for line in message.split("\n"):
        if THREAD.fullmatch(line):
            # Retain one systemd-listed stack. Never mix frames from multiple
            # threads or treat the first listed thread as a proven crash thread.
            if in_stack:
                partial = truncated = True
                break
            in_stack = True
            continue
        if not in_stack or not line.startswith("#"):
            continue
        match = FRAME.fullmatch(line)
        if match is None:
            partial = True
            continue
        pc, symbol, module, offset = match.groups()
        module = approved_module(module)
        if module is None or int(offset, 16) >= int(pc, 16):
            partial = True
            continue
        if len(frames) == FRAME_LIMIT:
            partial = truncated = True
            break
        safe_frame = {"module": module, "offset": hex(int(offset, 16))}
        if symbol in MODULE_SYMBOLS[module]:
            safe_frame["symbol"] = symbol
        else:
            partial = True
        frames.append(safe_frame)
    return frames, partial or not frames, truncated


def collect(result, data, cut, since, until):
    if cut:
        # A partial trailing line could be an incomplete valid record.
        data = data[:data.rfind(b"\n") + 1]
    malformed = 0
    first_us, last_us = since * 1_000_000, (until + 1) * 1_000_000
    for line in data.split(b"\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line.decode("utf-8"), object_pairs_hook=unique_fields,
                             parse_constant=invalid_constant)
            if not isinstance(row, dict):
                raise ValueError
            timestamp = number(row.get("COREDUMP_TIMESTAMP"), 18)
            pid = number(row.get("COREDUMP_PID"), 10)
            exe = row.get("COREDUMP_EXE")
            sig = row.get("COREDUMP_SIGNAL_NAME")
            if (timestamp < 1_000_000 or pid > 2_147_483_647 or not isinstance(exe, str)
                    or not isinstance(sig, str) or sig not in SIGNALS):
                raise ValueError
        except (ValueError, RecursionError):
            malformed += 1
            result["rejected_records"] += 1
            continue
        role = ROLES.get(exe)
        if role is None or not first_us <= timestamp < last_us:
            result["rejected_records"] += 1
            continue
        if len(result["records"]) == RECORD_LIMIT:
            cut = True
            continue
        frames, partial, limited = stack(row.get("MESSAGE"))
        result["records"].append({
            "pid": pid, "timestamp_us": timestamp, "signal": sig, "role": role,
            "partial": partial, "frames": frames,
        })
        cut |= limited
    if result["availability"] == "available" and not result["records"]:
        result["availability"] = "truncated" if cut else "malformed" if malformed else "empty"
    result["truncated"] = cut
    result["partial"] = bool(
        cut or malformed or any(record["partial"] for record in result["records"])
    )


def export(result):
    def encode():
        return json.dumps(result, separators=(",", ":"), ensure_ascii=True)

    payload = encode()
    while len(payload) + 1 > EXPORT_LIMIT and result["records"]:
        result["records"].pop()
        result["truncated"] = result["partial"] = True
        payload = encode()
    print(payload)


def main():
    parser = PrivateParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--journal-jsonl", metavar="FILE")
    try:
        options = parser.parse_args()
        since, until = number(options.since, 12), number(options.until, 12)
        # journalctl must be able to represent both times in ordinary UTC.
        if since > until or until > 253402300799:
            raise ValueError
    except ValueError:
        export(summary("invalid_window"))
        return 2

    handler = "not_checked" if options.journal_jsonl is not None else core_handler()
    result = summary(handler=handler)
    try:
        availability, data, cut = (
            replay(options.journal_jsonl) if options.journal_jsonl is not None else query(since, until)
        )
        result = summary(availability, handler)
        if availability in ("available", "timeout"):
            collect(result, data, cut, since, until)
    except (OSError, subprocess.SubprocessError, ValueError):
        result = summary(handler=handler)
    export(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
