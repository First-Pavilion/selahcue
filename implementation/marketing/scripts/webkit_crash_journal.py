"""Read existing systemd crash summaries for the pinned hosted WebKit sweep.

--since and --until are inclusive UTC epoch seconds. --journal-jsonl replays a
regular file without consulting the host journal or core handler. A diagnostic
result (including unavailable, timeout, or malformed) exits 0; an invalid
window or invocation emits the same safe schema and exits 2.
"""
import argparse
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time


RAW_LIMIT = 256 * 1024
EXPORT_LIMIT = 24 * 1024
RECORD_LIMIT = 3
THREAD_LIMIT = 64
STACK_EXPORT_LIMIT = 3
FRAME_LIMIT = 12
MODULE_ID_LIMIT = 16
WINDOW_SECONDS = 3600
MAX_TID = 2_147_483_647
# Reserve time within five seconds for signaling the sudo supervisor and reaping.
QUERY_SECONDS = 4
TERMINATION_GRACE = 0.15
REAP_SECONDS = 0.5
MESSAGE_ID = "fc2e22bc6ee647b6b90729ab34a250b1"
FIELDS = (
    "COREDUMP_TIMESTAMP,COREDUMP_PID,COREDUMP_SIGNAL_NAME,COREDUMP_EXE,COREDUMP_COMM,MESSAGE,"
    "_BOOT_ID,COREDUMP_TRUNCATED,COREDUMP_FILENAME,COREDUMP_PACKAGE_JSON"
)

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
PARITY_DEPS = Path(__file__).resolve().parents[3] / "implementation/desktop/target/debug/deps"
PARITY_NAME = re.compile(r"test_parity-[0-9a-f]{16}")
GPU_MODULES = {
    "libvulkan.so.1", "libvulkan_lvp.so", "libvulkan_intel.so", "libvulkan_radeon.so",
    "libEGL.so.1", "libEGL_mesa.so.0", "libGLdispatch.so.0", "libGLX.so.0", "libGLX_mesa.so.0",
}
THREAD = re.compile(r"Stack trace of thread ([1-9][0-9]{0,9}):")
ORDINAL = re.compile(r"#([0-9]{1,3})(?![0-9])")
FRAME = re.compile(
    r"#([0-9]{1,3}) +0x([0-9a-f]{1,16}) ([\x20-\x7e]*) "
    r"\(([!-~]+) \+ 0x([0-9a-f]{1,16})\)"
)
# Parse canonical spellings, but recognize malformed structural lines so they
# cannot silently change the owner or reliability of following frame evidence.
LEADING_CONTROL = re.compile(r"^[\x00-\x20]*")
MODULE_ID_LINE = re.compile(r"Module ([!-~]+), build-id=([0-9a-f]{8,128})")
BUILD_ID = re.compile(r"(?:[0-9a-f]{2}){4,64}")
BOOT_ID = re.compile(r"[0-9a-f]{32}")

class PrivateParser(argparse.ArgumentParser):
    def error(self, _message):
        raise ValueError


def number(value, digits):
    if not isinstance(value, str) or not re.fullmatch(rf"[1-9][0-9]{{0,{digits - 1}}}", value):
        raise ValueError
    return int(value)


def summary(availability="unavailable", handler="not_checked"):
    complete = availability in ("available", "empty")
    return {
        "schema_version": 2, "availability": availability, "handler": handler,
        "partial": availability != "empty", "truncated": False,
        "rejected_records": 0, "records": [], "candidate_scan_complete": complete,
        "export_truncated": False, "omission_reasons": [] if complete else ["join_incomplete"],
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
    # threshold (4096 bytes). The fixed field projection and our own read cap
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


def parity_executable(exe):
    path = Path(exe)
    if not PARITY_NAME.fullmatch(path.name) or exe != str(PARITY_DEPS / path.name):
        return None
    try:
        if path.resolve(strict=True) == path and path.is_file():
            return path
    except (OSError, RuntimeError, ValueError):
        pass
    return None


def approved_module(module, parity_exe=None):
    directory, slash, name = module.rpartition("/")
    if module in ROLES or (parity_exe and module == str(parity_exe)):
        return name
    if slash and directory not in MODULE_DIRS:
        return None
    if parity_exe and (name in GPU_MODULES or (not slash and name == parity_exe.name)):
        return name
    if name not in MODULE_SYMBOLS:
        versioned = VERSIONED_MODULE.fullmatch(name)
        name = versioned[1] if versioned else None
    return name if name in MODULE_SYMBOLS else None


def stack(message, parity_exe=None):
    threads = {}
    reasons = set()
    complete = True
    current = None
    ordinals = 0
    if not isinstance(message, str):
        return [], {"malformed", "ordinal_missing"}, False

    for line in message.split("\n"):
        possible = LEADING_CONTROL.sub("", line).lstrip()
        if possible.startswith("Stack trace of thread"):
            current = None
            match = THREAD.fullmatch(line)
            if not match or int(match[1]) > MAX_TID:
                complete = False
                reasons.add("malformed")
                continue
            tid = int(match[1])
            if tid in threads:
                complete = False
                reasons.add("malformed")
                threads[tid]["_frame_zero"] = None
                threads[tid]["frames"] = [f for f in threads[tid]["frames"] if f["ordinal"] != 0]
                continue
            if len(threads) == THREAD_LIMIT:
                complete = False
                reasons.add("thread_limit")
                continue
            current = {"tid": tid, "basis": "listed_only", "_listing_index": len(threads),
                       "_frame_zero": None, "frames": []}
            threads[tid] = current
            ordinals = 0
            continue

        if not possible.startswith("#"):
            continue
        if current is None:
            if not threads:
                complete = False
                reasons.add("malformed")
            continue

        ordinal_match = ORDINAL.match(possible)
        if ordinal_match is None:
            reasons.add("malformed")
            continue
        ordinal = int(ordinal_match[1])
        bit = 1 << ordinal
        frames = current["frames"]
        if ordinals & bit:
            reasons.add("malformed")
            if ordinal == 0:
                current["_frame_zero"] = None
            frames[:] = [f for f in frames if f["ordinal"] != ordinal]
            continue
        ordinals |= bit

        match = FRAME.fullmatch(line)
        if match is None:
            reasons.add("malformed")
            continue
        _, pc, symbol, module, offset = match.groups()
        module = approved_module(module, parity_exe)
        if module is None:
            reasons.add("module_filtered")
            continue
        pc, offset = int(pc, 16), int(offset, 16)
        if offset >= pc:
            reasons.add("malformed")
            continue

        frame = {"ordinal": ordinal, "module": module, "offset": hex(offset)}
        if symbol in MODULE_SYMBOLS.get(module, ()):
            frame["symbol"] = symbol
        else:
            reasons.add("symbol_filtered")

        if len(frames) == FRAME_LIMIT:
            reasons.add("frame_limit")
            if ordinal != 0:
                continue
            # The original #0 can occur after the storage cap. Retain it
            # without increasing the frame budget for this thread.
            frames.pop()
        frames.append(frame)
        if ordinal == 0:
            current["_frame_zero"] = {"pc": pc, "module": module, "frame": frame}

    if not threads or any(t["_frame_zero"] is None for t in threads.values()):
        reasons.add("ordinal_missing")
    if not threads:
        complete = False
    return list(threads.values()), reasons, complete


def module_identities(package_json, message, parity_exe, slots, reasons):
    identities = {}

    def add(module, build_id):
        nonlocal slots
        module = approved_module(module, parity_exe)
        if module is None:
            reasons.add("module_filtered")
            return
        if not isinstance(build_id, str) or not BUILD_ID.fullmatch(build_id):
            reasons.add("identity_missing")
            return
        if module in identities:
            if identities[module] != build_id:
                reasons.add("identity_conflict")
                identities[module] = None
        elif slots:
            identities[module] = build_id
            slots -= 1
        else:
            reasons.add("identity_missing")

    if package_json is not None:
        try:
            if not isinstance(package_json, str):
                raise ValueError
            package = json.loads(package_json, object_pairs_hook=unique_fields,
                                 parse_constant=invalid_constant)
            if not isinstance(package, dict):
                raise ValueError
        except (ValueError, RecursionError):
            # Optional identity metadata is independent of thread/PC inspection.
            reasons.add("malformed")
        else:
            for module, entry in package.items():
                if isinstance(entry, dict) and "buildId" in entry:
                    add(module, entry["buildId"])
    if isinstance(message, str):
        for line in message.split("\n"):
            if match := MODULE_ID_LINE.fullmatch(line):
                add(*match.groups())

    identities = {module: build_id for module, build_id in identities.items() if build_id is not None}
    if not identities:
        reasons.add("identity_missing")
    return identities, slots


def collect(result, data, cut, since, until, *, profile="webkit"):
    reasons = set(result["omission_reasons"])
    complete = result["candidate_scan_complete"]
    if len(data) > RAW_LIMIT:
        data, cut = data[:RAW_LIMIT], True
    if cut:
        # A partial trailing line could be an incomplete valid record.
        data = data[:data.rfind(b"\n") + 1]
        reasons.add("deadline" if result["availability"] == "timeout" else "raw_limit")
        complete = False

    malformed = 0
    identity_slots = MODULE_ID_LIMIT
    first_us, last_us = since * 1_000_000, (until + 1) * 1_000_000
    for line in data.split(b"\n"):
        if not line:
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
            if (timestamp < 1_000_000 or pid > MAX_TID or not isinstance(exe, str)
                    or not isinstance(sig, str) or sig not in SIGNALS):
                raise ValueError
        except (ValueError, RecursionError):
            malformed += 1
            result["rejected_records"] += 1
            complete = False
            reasons.add("malformed")
            continue
        if not first_us <= timestamp < last_us:
            result["rejected_records"] += 1
            continue
        parity_exe = parity_executable(exe) if profile == "gpu-parity" else None
        role = ("gpu_parity" if parity_exe else None) if profile == "gpu-parity" else ROLES.get(exe)
        if role is None:
            result["rejected_records"] += 1
            continue
        if len(result["records"]) == RECORD_LIMIT:
            complete = False
            reasons.add("record_limit")
            continue

        message = row.get("MESSAGE")
        threads, record_reasons, stack_complete = stack(message, parity_exe)
        identities, identity_slots = module_identities(
            row.get("COREDUMP_PACKAGE_JSON"), message, parity_exe, identity_slots, record_reasons,
        )
        boot_id = row.get("_BOOT_ID")
        if not isinstance(boot_id, str) or not BOOT_ID.fullmatch(boot_id):
            boot_id = None
        filename = row.get("COREDUMP_FILENAME")
        record = {
            "pid": pid, "timestamp_us": timestamp, "signal": sig, "role": role,
            "partial": bool(record_reasons), "threads": threads,
            "core_truncated": True if row.get("COREDUMP_TRUNCATED") == "1" else None,
            "core_storage": "external_reported" if isinstance(filename, str) and filename else "unknown",
            "module_identity": identities, "fault_attribution": {"fault_thread": None},
            "_boot_id": boot_id,
        }
        if parity_exe:
            record["executable"] = parity_exe.name
            record["_parity_exe"] = parity_exe
        result["records"].append(record)
        complete &= stack_complete
        reasons.update(record_reasons)

    if result["availability"] == "available" and not result["records"]:
        result["availability"] = "truncated" if cut else "malformed" if malformed else "empty"
    if not complete:
        reasons.add("join_incomplete")
    result["candidate_scan_complete"] = complete
    result["export_truncated"] = "frame_limit" in reasons
    result["truncated"] = bool(reasons & {"raw_limit", "deadline", "record_limit", "thread_limit", "frame_limit"})
    result["partial"] = bool(reasons)
    result["omission_reasons"] = sorted(reasons)


def export(result):
    # Only these fields cross the public boundary. Absolute PCs, boot IDs and
    # canonical installed paths are private even when the stack was selected.
    payload = {key: result[key] for key in (
        "schema_version", "availability", "handler", "partial", "truncated",
        "rejected_records", "candidate_scan_complete", "export_truncated", "omission_reasons",
    )}
    records = payload["records"] = []

    def mark_export_limit():
        payload["truncated"] = payload["partial"] = payload["export_truncated"] = True
        payload["omission_reasons"] = sorted({*payload["omission_reasons"], "export_limit"})

    for record in result["records"]:
        safe = {key: record[key] for key in (
            "pid", "timestamp_us", "signal", "role", "partial", "core_truncated",
            "core_storage", "module_identity",
        )}
        safe["fault_attribution"] = {"fault_thread": None}
        if "executable" in record:
            safe["executable"] = record["executable"]
        threads = safe["threads"] = []
        for thread in record["threads"][:STACK_EXPORT_LIMIT]:
            threads.append({
                "tid": thread["tid"], "basis": "listed_only",
                "frames": [
                    {key: frame[key] for key in ("ordinal", "module", "offset", "symbol") if key in frame}
                    for frame in thread["frames"]
                ],
            })
        if len(record["threads"]) > STACK_EXPORT_LIMIT:
            safe["partial"] = True
            mark_export_limit()
        records.append(safe)

    def encode():
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)

    encoded = encode()
    if len(encoded) + 1 > EXPORT_LIMIT:
        mark_export_limit()
        for record in reversed(records):
            while record["threads"] and len(encoded) + 1 > EXPORT_LIMIT:
                frames = record["threads"][-1]["frames"]
                if frames:
                    frames.pop()
                else:
                    record["threads"].pop()
                record["partial"] = True
                encoded = encode()
        while records and len(encoded) + 1 > EXPORT_LIMIT:
            records.pop()
            encoded = encode()
    print(encoded)


def main():
    parser = PrivateParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--journal-jsonl", metavar="FILE")
    parser.add_argument("--profile", choices=("webkit", "gpu-parity"), default="webkit")
    try:
        options = parser.parse_args()
        since, until = number(options.since, 12), number(options.until, 12)
        # journalctl must be able to represent both times in ordinary UTC.
        if since > until or until - since >= WINDOW_SECONDS or until > 253402300799:
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
            collect(result, data, cut, since, until, profile=options.profile)
    except (OSError, subprocess.SubprocessError, ValueError):
        result = summary(handler=handler)
    export(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
