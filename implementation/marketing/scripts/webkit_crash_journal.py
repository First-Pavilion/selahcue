"""Read existing systemd crash summaries for the pinned hosted WebKit sweep.

--since and --until are inclusive UTC epoch seconds. --journal-jsonl replays a
regular file without consulting the host journal or core handler. Use --kernel-jsonl only
with that offline replay. A diagnostic
result (including unavailable, timeout, or malformed) exits 0; an invalid
window or invocation emits the same safe schema and exits 2.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import struct
import subprocess
import sys
import time


RAW_LIMIT = 256 * 1024
KERNEL_LIMIT = 64 * 1024
KERNEL_LINE_LIMIT = 4096
EXPORT_LIMIT = 24 * 1024
RECORD_LIMIT = 3
THREAD_LIMIT = 64
STACK_EXPORT_LIMIT = 3
FRAME_LIMIT = 12
MODULE_ID_LIMIT = 16
WINDOW_SECONDS = 3600
MAX_TID = 2_147_483_647
MAX_EPOCH_SECONDS = 253402300799
FAULT_BASIS = "kernel_tid_and_frame0_pc"
METADATA_SECONDS = 8
IDENTITY_SECONDS = 2
OUTPUT_RESERVE_SECONDS = 0.05
# Reserve time within five seconds for signaling the sudo supervisor and reaping.
QUERY_SECONDS = 4
KERNEL_QUERY_SECONDS = 2
TERMINATION_GRACE = 0.15
REAP_SECONDS = 0.5
CLEANUP_SECONDS = TERMINATION_GRACE + REAP_SECONDS
KERNEL_FIELDS = "MESSAGE,__REALTIME_TIMESTAMP,_BOOT_ID,_TRANSPORT"
MESSAGE_ID = "fc2e22bc6ee647b6b90729ab34a250b1"
FIELDS = (
    "COREDUMP_TIMESTAMP,COREDUMP_PID,COREDUMP_SIGNAL_NAME,COREDUMP_EXE,COREDUMP_COMM,MESSAGE,"
    "_BOOT_ID,COREDUMP_TRUNCATED,COREDUMP_FILENAME,COREDUMP_PACKAGE_JSON"
)

# The hosted log fixes the cache root and revision. The pinned Playwright
# registry identifies the WPE bin directory; the WebKit WPE build names its
# helpers. pw_run.sh and the MiniBrowser shell wrapper are not ELF crash roles.
BUNDLE = "/home/runner/.cache/ms-playwright/webkit-2388/minibrowser-wpe"
WPE_MODULE = "libWPEWebKit-2.0.so.1"
WPE_LIBRARY = Path(BUNDLE) / "lib" / WPE_MODULE
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
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PARITY_DEPS = REPOSITORY_ROOT / "implementation/desktop/target/debug/deps"
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
LEADING_CONTROL = re.compile(r"^[\s\x00-\x1f\x7f]*")
THREAD_START = re.compile(r"Stack[\s\x00-\x1f\x7f]*trace", re.IGNORECASE)
MODULE_ID_LINE = re.compile(r"Module ([!-~]+), build-id=([0-9a-f]{8,128})")
BUILD_ID = re.compile(r"(?:[0-9a-f]{2}){4,64}")
BOOT_ID = re.compile(r"[0-9a-f]{32}")


KERNEL_HEX = r"[0-9a-f]{1,16}"
KERNEL_PREFIX = re.compile(
    rf"(?:(?![\[\]])[ -~]){{1,64}}\[(?P<tid>[0-9]{{1,10}})\]: segfault at {KERNEL_HEX} "
    rf"ip (?P<pc>[0-9a-f]{{16}}) sp [0-9a-f]{{16}} error {KERNEL_HEX}(?P<ending>[ -~]*)"
)
KERNEL_ENDING = re.compile(
    rf"(?: in (?P<module>[A-Za-z0-9_.-]+)\[(?:(?P<third>{KERNEL_HEX}),)?"
    rf"{KERNEL_HEX}\+{KERNEL_HEX}\])?"
    r"(?: likely on CPU (?P<cpu>[0-9]{1,10}) \(core (?P<core>-?[0-9]{1,10}), "
    r"socket (?P<socket>-?[0-9]{1,10})\))?"
)
ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
ELF_PROGRAM = struct.Struct("<IIQQQQQQ")
ELF_NOTE = struct.Struct("<III")
ELF_FILE_LIMIT = 256 * 1024 * 1024
ELF_CHUNK = ELF_NOTE_LIMIT = 1024 * 1024
ELF_HEADER_LIMIT = 128
IDENTITY_CHILD = (
    "import json,runpy,sys; from pathlib import Path; "
    "read=runpy.run_path(sys.argv[1])['read_elf_identity']; "
    "print(json.dumps(read(Path(sys.argv[2]), expected_root=Path(sys.argv[3]), "
    "include_resolved_basename=sys.argv[4] == 'webkit')))"
)


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


def replay(path, limit=RAW_LIMIT):
    # Opening a FIFO with ordinary read flags would block before fstat.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    # Keep the one-byte overflow probe from filling a read-ahead buffer.
    with os.fdopen(fd, "rb", buffering=0) as source:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return "unavailable", b"", False
        data = bytearray()
        while len(data) < limit:
            chunk = source.read(limit - len(data))
            if not chunk:
                return "available", data, False
            data.extend(chunk)
        return "available", data, bool(source.read(1))


def signal_group(child, sig):
    try:
        os.killpg(child.pid, sig)
        return True
    except ProcessLookupError:
        return True
    except PermissionError:
        return False


def stop_owned_group(child, deadline, *, exited=False):
    # The leader is intentionally unreaped while signaling its group, so
    # neither an inherited pipe nor a reused PID can redirect the cleanup.
    confirmed = True
    if not exited:
        confirmed = signal_group(child, signal.SIGTERM)
        time.sleep(max(0, min(TERMINATION_GRACE, deadline - time.monotonic() - REAP_SECONDS)))
    confirmed &= signal_group(child, signal.SIGKILL)
    try:
        child.wait(timeout=max(0, min(REAP_SECONDS, deadline - time.monotonic())))
    except subprocess.TimeoutExpired:
        return False
    if not confirmed and exited and sys.platform == "darwin":
        # Darwin can report EPERM for an unreaped zombie. With the
        # leader reaped, require an independent absence check; never
        # signal a potentially reused group ID.
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
    return confirmed


def read_child(args, limit, read_deadline, cleanup_deadline):
    data = bytearray()
    if time.monotonic() >= read_deadline:
        return "timeout", data, False, True
    try:
        child = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable", data, False, True

    outcome, cut, exited = "unavailable", False, False
    try:
        fd = child.stdout.fileno()
        os.set_blocking(fd, False)
        with selectors.DefaultSelector() as watcher:
            watcher.register(fd, selectors.EVENT_READ)
            while True:
                remaining = read_deadline - time.monotonic()
                if remaining <= 0 or not watcher.select(remaining):
                    outcome, cut = "timeout", True
                    break
                room = limit - len(data)
                try:
                    chunk = os.read(fd, min(8192, room) if room else 1)
                except BlockingIOError:
                    continue
                if not chunk:
                    while time.monotonic() < read_deadline:
                        # Observe without reaping: a descendant may have
                        # closed stdout and still need to be terminated.
                        status = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                        if status and status.si_pid:
                            exited = True
                            if status.si_code == os.CLD_EXITED and status.si_status == 0:
                                outcome = "available"
                            break
                        time.sleep(max(0, min(0.005, read_deadline - time.monotonic())))
                    else:
                        outcome, cut = "timeout", True
                    break
                if not room:
                    outcome, cut = "available", True
                    break
                data.extend(chunk)
    except OSError:
        outcome, cut = "unavailable", False
    finally:
        child.stdout.close()
        reaped = stop_owned_group(child, cleanup_deadline, exited=exited)
    return outcome, data if outcome != "unavailable" else b"", cut, reaped


def journal_args(since, until, selector, projection):
    # --all retains MESSAGE fields over journalctl's default 4096 bytes.
    return [
        "sudo", "-n", "journalctl", "-b", "--no-pager", "--quiet", "--all",
        "--since", f"@{since}", "--until", f"@{until}.999999",
        selector, "-o", "json", f"--output-fields={projection}",
    ]


def query(since, until, deadline):
    read_until = time.monotonic() + QUERY_SECONDS
    cleanup_until = min(deadline, read_until + CLEANUP_SECONDS)
    return read_child(journal_args(since, until, f"MESSAGE_ID={MESSAGE_ID}", FIELDS),
                      RAW_LIMIT, min(read_until, cleanup_until - CLEANUP_SECONDS), cleanup_until)


def query_kernel(since, until, deadline):
    # Preserve the crash window; only kernel acquisition gets the two-second
    # correlation tail. The isolated process still has a two-second read cap.
    read_until = time.monotonic() + KERNEL_QUERY_SECONDS
    cleanup_until = min(deadline, read_until + CLEANUP_SECONDS)
    args = journal_args(since, min(until + 2, MAX_EPOCH_SECONDS), "_TRANSPORT=kernel", KERNEL_FIELDS)
    return read_child(args, KERNEL_LIMIT, min(read_until, cleanup_until - CLEANUP_SECONDS), cleanup_until)


class DiagnosticDeadline(Exception):
    pass


@contextmanager
def time_bound(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DiagnosticDeadline

    def expired(_signum, _frame):
        raise DiagnosticDeadline

    previous = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, remaining)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


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
        possible = LEADING_CONTROL.sub("", line)
        if THREAD_START.match(possible):
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
        # An unclassifiable ordinal may be a competing zero. Reserve that
        # ordinal so the duplicate check handles either order of the lines.
        ordinal = int(ordinal_match[1]) if ordinal_match else 0
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
    result["_profile"] = profile
    reasons = set(result["omission_reasons"])
    complete = result["candidate_scan_complete"]
    record_population_complete = complete
    if len(data) > RAW_LIMIT:
        data, cut = data[:RAW_LIMIT], True
    if cut:
        # A partial trailing line could be an incomplete valid record.
        data = data[:data.rfind(b"\n") + 1]
        reasons.add("deadline" if result["availability"] == "timeout" else "raw_limit")
        complete = record_population_complete = False

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
            complete = record_population_complete = False
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
            complete = record_population_complete = False
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
    result["_record_population_complete"] = record_population_complete
    result["export_truncated"] = "frame_limit" in reasons
    result["truncated"] = bool(reasons & {"raw_limit", "deadline", "record_limit", "thread_limit", "frame_limit"})
    result["partial"] = bool(reasons)
    result["omission_reasons"] = sorted(reasons)



def _kernel_message_details(message, parity_names=()):
    if (not isinstance(message, str) or len(message) > KERNEL_LINE_LIMIT
            or not message.isascii()):
        return None, "text_bounds", None
    match = KERNEL_PREFIX.fullmatch(message.removesuffix("\n"))
    if not match:
        return None, "prefix_shape", None
    tid, pc, ending = int(match["tid"]), int(match["pc"], 16), match["ending"]
    if not 1 <= tid <= MAX_TID:
        return None, "numeric_range", None
    module = None
    if ending:
        suffix = KERNEL_ENDING.fullmatch(ending)
        if not suffix:
            return None, "suffix_shape", None
        module = suffix["module"]
        refused = module is not None and module not in MODULE_SYMBOLS and module not in parity_names
        # Keep module-policy priority while observing the same later checks.
        non_module_stage = None
        cpu = suffix["cpu"]
        if cpu is None:
            if module is None or suffix["third"] is not None:
                non_module_stage = "producer_ending"
        elif not (int(cpu) <= MAX_TID
                  and all(-2_147_483_648 <= int(suffix[name]) <= MAX_TID for name in ("core", "socket"))):
            non_module_stage = "numeric_range"
        if refused:
            return None, "module_policy", {
                "tid": tid, "pc": pc, "module_token": module,
                "non_module_valid": non_module_stage is None,
            }
        if non_module_stage is not None:
            return None, non_module_stage, None
    return (tid, pc, module), None, None


def _parse_kernel_message(message, parity_names=()):
    return _kernel_message_details(message, parity_names)[:2]


def parse_kernel_message(message, parity_names=()):
    return _parse_kernel_message(message, parity_names)[0]


def _kernel_candidate_check(event, boot_id, timestamp, record, thread, *, compare_module):
    tid, pc, module = event
    if record["signal"] != "SIGSEGV" or thread["tid"] != tid:
        return "excluded"
    if not 0 <= timestamp - record["timestamp_us"] < 2_000_000:
        return "excluded"
    if record["_boot_id"] is None:
        return "missing_boot"
    if record["_boot_id"] != boot_id:
        return "excluded"
    zero = thread["_frame_zero"]
    if zero is None:
        return "missing_zero"
    if pc != zero["pc"] or compare_module and module is not None and module != zero["module"]:
        return "excluded"
    return "match"


MODULE_RELATIONS = (
    "structurally_invalid", "no_retained_candidate", "one_retained_candidate",
    "multiple_retained_candidates", "indeterminate",
)
MODULE_BUCKETS = ("resolved_wpe_alias", "other_rejected", "unknown_alias")
MODULE_OBSERVATION_LIMIT = 1024


def _wpe_basename(value):
    if not isinstance(value, str) or not value.isascii() or len(value) > 64:
        return False
    versioned = VERSIONED_MODULE.fullmatch(value)
    return value == WPE_MODULE or bool(versioned and versioned[1] == WPE_MODULE)


def _observe_module_rejection(state, detail, relation):
    state["seen"] = True
    token = detail["module_token"]
    if not _wpe_basename(token):
        counts = state["buckets"]["other_rejected"]
    elif token in state["aliases"]:
        counts = state["aliases"][token]
    elif len(state["aliases"]) < 8:
        counts = state["aliases"][token] = dict.fromkeys(MODULE_RELATIONS, 0)
    else:
        counts = state["buckets"]["unknown_alias"]
        state["limit_hit"] = state["partial"] = True
    counts[relation] = min(2, counts[relation] + 1)


def _finalize_module_rejections(state, resolved_wpe_basename):
    available = _wpe_basename(resolved_wpe_basename)
    buckets = {name: dict(counts) for name, counts in state["buckets"].items()}
    for token, counts in state["aliases"].items():
        bucket = ("unknown_alias" if not available else
                  "resolved_wpe_alias" if token == resolved_wpe_basename else "other_rejected")
        for relation in MODULE_RELATIONS:
            buckets[bucket][relation] = min(2, buckets[bucket][relation] + counts[relation])
    return {
        "version": 1, "coverage": "partial" if state["partial"] else "complete",
        "alias_resolution": "available" if available else "unavailable",
        "pending_alias_limit_hit": state["limit_hit"], "buckets": buckets,
    }


def safe_module_observation(value):
    if (type(value) is not dict or set(value) != {
            "version", "coverage", "alias_resolution", "pending_alias_limit_hit", "buckets"}
            or type(value["version"]) is not int or value["version"] != 1
            or value["coverage"] not in ("complete", "partial")
            or value["alias_resolution"] not in ("available", "unavailable")
            or type(value["pending_alias_limit_hit"]) is not bool):
        return None
    buckets = value["buckets"]
    if type(buckets) is not dict or set(buckets) != set(MODULE_BUCKETS):
        return None
    copied = {}
    for name in MODULE_BUCKETS:
        counts = buckets[name]
        if (type(counts) is not dict or set(counts) != set(MODULE_RELATIONS)
                or any(type(counts[key]) is not int or not 0 <= counts[key] <= 2
                       for key in MODULE_RELATIONS)):
            return None
        copied[name] = {key: counts[key] for key in MODULE_RELATIONS}
    safe = {key: value[key] for key in ("version", "coverage", "alias_resolution", "pending_alias_limit_hit")}
    safe["buckets"] = copied
    if len(json.dumps(safe, separators=(",", ":"), ensure_ascii=True)) > MODULE_OBSERVATION_LIMIT:
        return None
    return safe


def correlate_kernel(records, kernel_bytes, candidate_scan_complete, *, diagnostics=None,
                     profile="webkit", observation_complete=True):
    reasons = set()
    rejection_stage = None
    observation = ({"buckets": {name: dict.fromkeys(MODULE_RELATIONS, 0) for name in MODULE_BUCKETS},
                    "aliases": {}, "seen": False, "partial": not observation_complete,
                    "limit_hit": False} if profile == "webkit" else None)
    indexed_threads = {}
    parity_names = set()
    for record in records:
        record["fault_attribution"] = {"fault_thread": None}
        if "_parity_exe" in record:
            parity_names.update(GPU_MODULES)
            parity_names.add(record["_parity_exe"].name)
        if record["signal"] == "SIGSEGV":
            for thread in record["threads"]:
                indexed_threads.setdefault(thread["tid"], []).append((record, thread))

    pairs = 0
    candidate_pair = None
    if kernel_bytes is None:
        reasons.add("kernel_unavailable")
    else:
        if len(kernel_bytes) > KERNEL_LIMIT:
            reasons.add("kernel_limit")
            if observation is not None:
                observation["partial"] = True
            kernel_bytes = kernel_bytes[:KERNEL_LIMIT]
            kernel_bytes = kernel_bytes[:kernel_bytes.rfind(b"\n") + 1]

        for line in kernel_bytes.split(b"\n"):
            if not line:
                continue
            try:
                row = json.loads(line.decode("utf-8"), object_pairs_hook=unique_fields,
                                 parse_constant=invalid_constant)
                if not isinstance(row, dict):
                    raise ValueError
                message, boot_id = row.get("MESSAGE"), row.get("_BOOT_ID")
                if (row.get("_TRANSPORT") != "kernel" or not isinstance(message, str)
                        or not isinstance(boot_id, str) or not BOOT_ID.fullmatch(boot_id)):
                    raise ValueError
                timestamp = number(row.get("__REALTIME_TIMESTAMP"), 18)
                if timestamp < 1_000_000:
                    raise ValueError
            except (ValueError, RecursionError):
                reasons.add("malformed")
                if observation is not None:
                    observation["partial"] = True
                continue
            if "segfault" not in message:
                continue
            event, stage, detail = _kernel_message_details(message, parity_names)
            if event is None:
                rejection_stage = stage if rejection_stage is None else (
                    rejection_stage if rejection_stage == stage else "mixed"
                )
                reasons.add("kernel_unsupported_format")
                if observation is not None:
                    if detail is None:
                        observation["partial"] = True
                    else:
                        relation = "structurally_invalid"
                        if detail["non_module_valid"]:
                            matches, unresolved = 0, False
                            private_event = (detail["tid"], detail["pc"], None)
                            try:
                                for record, thread in indexed_threads.get(detail["tid"], ()):
                                    check = _kernel_candidate_check(
                                        private_event, boot_id, timestamp, record, thread, compare_module=False,
                                    )
                                    matches = min(2, matches + (check == "match"))
                                    unresolved |= check in ("missing_boot", "missing_zero")
                                relation = ("indeterminate" if unresolved else
                                            ("no_retained_candidate", "one_retained_candidate",
                                             "multiple_retained_candidates")[matches])
                            except (KeyError, TypeError, ValueError):
                                relation = "indeterminate"
                                observation["partial"] = True
                        observation["seen"] = True
                        try:
                            _observe_module_rejection(observation, detail, relation)
                        except (KeyError, TypeError, ValueError):
                            observation["partial"] = True
                continue
            tid = event[0]
            for record, thread in indexed_threads.get(tid, ()):
                check = _kernel_candidate_check(event, boot_id, timestamp, record, thread, compare_module=True)
                if check == "missing_boot":
                    reasons.add("malformed")
                elif check == "missing_zero":
                    reasons.add("ordinal_missing")
                elif check == "match":
                    pairs += 1
                    if pairs == 1:
                        candidate_pair = (record, tid, timestamp - record["timestamp_us"], thread["_frame_zero"]["frame"])

    complete = candidate_scan_complete and not reasons
    if not complete:
        reasons.add("join_incomplete")
    elif not pairs:
        reasons.add("kernel_no_match")
    elif pairs > 1:
        reasons.add("kernel_ambiguous")
    else:
        record, tid, delta, frame = candidate_pair
        record["fault_attribution"]["fault_thread"] = {
            "tid": tid, "basis": FAULT_BASIS, "delta_us": delta, "frame_zero": frame,
        }
    if diagnostics is not None and observation is not None and observation["seen"]:
        diagnostics["_module_rejections"] = observation
        diagnostics["kernel_module_policy_observation"] = _finalize_module_rejections(observation, None)
    if diagnostics is not None and rejection_stage is not None:
        diagnostics["kernel_rejection_stage"] = rejection_stage
    return records, complete, reasons


def resolved_identity_path(path, expected_root):
    resolved = path.resolve(strict=True)
    if resolved.parent != expected_root:
        raise ValueError
    # WebKit permits only the pinned SONAME resolving to itself or its exact
    # versioned family; the parity executable must already be canonical.
    if resolved != path:
        versioned = VERSIONED_MODULE.fullmatch(resolved.name)
        if path.name != WPE_MODULE or not versioned or versioned[1] != WPE_MODULE:
            raise ValueError
    return resolved


def open_fixed_directory(path):
    # Open each canonical component without following symlinks, so replacing
    # an ancestor between resolve and open cannot redirect the file read.
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for name in path.parts[1:]:
            successor = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = successor
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_exact(source, length):
    data = source.read(length)
    if len(data) != length:
        raise ValueError
    return data


def elf_build_id(source, size):
    header = ELF_HEADER.unpack(read_exact(source, ELF_HEADER.size))
    ident, _, machine, version, _, offset, _, _, hsize, entsize, count, *_ = header
    if (ident[:7] != b"\x7fELF\x02\x01\x01" or machine != 62 or version != 1
            or hsize != ELF_HEADER.size or count > ELF_HEADER_LIMIT):
        raise ValueError
    if offset > size:
        raise ValueError
    if count == 0:
        return None
    if (entsize != ELF_PROGRAM.size or offset < ELF_HEADER.size
            or offset + count * entsize > size):
        raise ValueError
    source.seek(offset)
    programs = [ELF_PROGRAM.unpack(read_exact(source, entsize)) for _ in range(count)]
    note_total, build_id = 0, None
    for kind, _, offset, _, _, length, _, alignment in programs:
        if offset + length > size:
            raise ValueError
        if kind != 4 or not length:  # PT_NOTE
            continue
        note_total += length
        if (offset < ELF_HEADER.size or note_total > ELF_NOTE_LIMIT
                or alignment not in (0, 1, 2, 4, 8)):
            raise ValueError
        source.seek(offset)
        notes = read_exact(source, length)
        align = max(4, alignment)
        cursor = 0
        while cursor < length:
            if cursor + ELF_NOTE.size > length:
                raise ValueError
            name_size, desc_size, note_type = ELF_NOTE.unpack_from(notes, cursor)
            name = cursor + ELF_NOTE.size
            desc = (name + name_size + align - 1) & -align
            end = desc + desc_size
            cursor = (end + align - 1) & -align
            if cursor > length:
                raise ValueError
            if note_type == 3 and name_size == 4 and notes[name:name + name_size] == b"GNU\0":
                if not 4 <= desc_size <= 64:
                    raise ValueError
                value = notes[desc:end].hex()
                if build_id is not None and build_id != value:
                    raise ValueError
                build_id = value
    return build_id


def read_elf_identity(path, *, expected_root, include_resolved_basename=False):
    try:
        resolved = resolved_identity_path(path, expected_root)
        before = resolved.stat()
        directory = open_fixed_directory(expected_root)
        try:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open(resolved.name, flags, dir_fd=directory)
        finally:
            os.close(directory)

        def unchanged(current):
            return (stat.S_ISREG(current.st_mode)
                    and (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                    == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns))

        with os.fdopen(fd, "rb", buffering=0) as source:
            if not unchanged(os.fstat(fd)) or not ELF_HEADER.size <= before.st_size <= ELF_FILE_LIMIT:
                return None
            build_id = elf_build_id(source, before.st_size)
            source.seek(0)
            digest = hashlib.sha256()
            remaining = before.st_size
            while remaining:
                chunk = read_exact(source, min(ELF_CHUNK, remaining))
                digest.update(chunk)
                remaining -= len(chunk)
            if (not unchanged(os.fstat(fd)) or resolved_identity_path(path, expected_root) != resolved
                    or not unchanged(resolved.stat())):
                return None
            identity = {"sha256": digest.hexdigest(), "build_id": build_id}
            if include_resolved_basename:
                identity["_resolved_basename"] = resolved.name
            return identity
    except (OSError, RuntimeError, ValueError, struct.error):
        return None


def installed_identity(profile, eligible_records, *, deadline=None, private_observation=None):
    if private_observation is not None:
        private_observation.pop("_resolved_basename", None)
    if profile == "webkit":
        path, module, root = WPE_LIBRARY, WPE_MODULE, WPE_LIBRARY.parent
    elif profile == "gpu-parity" and len(eligible_records) == 1:
        path = eligible_records[0].get("_parity_exe")
        if path is None or path.parent != PARITY_DEPS or not PARITY_NAME.fullmatch(path.name):
            return None, {"identity_missing"}
        module, root = path.name, PARITY_DEPS
    else:
        return None, {"identity_missing"}
    end = time.monotonic() + IDENTITY_SECONDS
    if deadline is not None:
        end = min(end, deadline)
    # Fixed owned Python child, isolated from caller imports/site config. It
    # receives only the path selected above and returns a tiny safe receipt.
    args = [sys.executable, "-I", "-B", "-c", IDENTITY_CHILD,
            __file__, str(path), str(root), profile]
    status, data, cut, reaped = read_child(args, 1024, end - CLEANUP_SECONDS, end)
    reasons = set()
    if not reaped:
        reasons.add("reap_unconfirmed")
    if status == "timeout":
        reasons.add("deadline")
    if status == "available" and not cut and reaped and len(data) <= 1024:
        try:
            receipt = json.loads(data, object_pairs_hook=unique_fields)
            keys = {"sha256", "build_id", "_resolved_basename"} if profile == "webkit" else {"sha256", "build_id"}
            if (isinstance(receipt, dict) and set(receipt) == keys
                    and (profile != "webkit" or _wpe_basename(receipt["_resolved_basename"]))):
                sha, build_id = receipt["sha256"], receipt["build_id"]
                if (isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)
                        and (build_id is None or isinstance(build_id, str) and BUILD_ID.fullmatch(build_id))):
                    if profile == "webkit" and private_observation is not None:
                        private_observation["_resolved_basename"] = receipt["_resolved_basename"]
                    return {"module": module, "sha256": sha, "build_id": build_id}, reasons
        except (ValueError, RecursionError):
            pass
    return None, reasons | {"identity_missing"}


SOURCE_SECONDS = 0.5
SOURCE_OUTPUT_LIMIT = 4096
SOURCE_LOCK_LIMIT = 1024 * 1024
KERNEL_REJECTION_STAGES = frozenset((
    "text_bounds", "prefix_shape", "numeric_range", "suffix_shape",
    "module_policy", "producer_ending", "mixed",
))
SOURCE_PATTERNS = {
    "checkout_sha": r"[0-9a-f]{40}", "tree_sha": r"[0-9a-f]{40}",
    "candidate_source_sha": r"[0-9a-f]{40}",
    "run_id": r"[0-9]{1,20}", "run_attempt": r"[0-9]{1,20}",
    "kernel_release": r"[A-Za-z0-9._+\-]{1,64}", "systemd_version": r"[0-9]{1,10}",
    "lock_sha256": r"[0-9a-f]{64}",
}


def safe_source_receipt(receipt):
    # Revalidate at export too: private command output and unknown keys never cross.
    profile = receipt.get("profile")
    if profile not in ("webkit", "gpu-parity"):
        return None
    patterns = dict(SOURCE_PATTERNS)
    if profile == "webkit":
        patterns.update(playwright_version=r"1\.65\.2", webkit_revision=r"2388")
    else:
        patterns["rust_channel"] = r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"
    safe = {"profile": profile, "job": "marketing" if profile == "webkit" else "rust"}
    for key, pattern in patterns.items():
        value = receipt.get(key)
        safe[key] = value if isinstance(value, str) and re.fullmatch(pattern, value) else None
    safe["complete"] = all(safe[key] is not None for key in patterns)
    return safe


def read_source_file(relative, limit):
    # Fixed caller paths only. Nonblocking open plus no-follow directory walking
    # rejects FIFOs, devices and symlink ancestors without touching their contents.
    path = REPOSITORY_ROOT / relative
    directory = open_fixed_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
        with os.fdopen(fd, "rb", buffering=0) as source:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise ValueError
            data = source.read(limit + 1)
            after = os.fstat(fd)
            named = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
            if (len(data) > limit or len(data) != before.st_size
                    or identity(before) != identity(after) or identity(before) != identity(named)):
                raise ValueError
            return data
    finally:
        os.close(directory)


def source_receipt(profile, candidate_source_sha, *, deadline):
    receipt = {"profile": profile, "candidate_source_sha": candidate_source_sha,
               "run_id": os.environ.get("GITHUB_RUN_ID"),
               "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")}
    # Both children share one budget, including cleanup. Reserve a small slice
    # for immediate KILL/reap instead of the query supervisor's full 0.65s.
    probe_deadline = min(deadline, time.monotonic() + SOURCE_SECONDS)
    remaining_bytes = SOURCE_OUTPUT_LIMIT
    for name, args in (
        ("git", ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD", "HEAD^{tree}"]),
        ("systemd", ["systemd", "--version"]),
    ):
        if remaining_bytes <= 0 or time.monotonic() >= probe_deadline - 0.05:
            break
        status, data, cut, reaped = read_child(args, remaining_bytes, probe_deadline - 0.05, probe_deadline)
        remaining_bytes -= len(data)
        if status != "available" or cut or not reaped:
            # The supervisor deliberately discards nonzero output. Stop here
            # rather than accidentally giving another child a fresh byte cap.
            break
        if name == "git":
            match = re.fullmatch(rb"([0-9a-f]{40})\n([0-9a-f]{40})\n", data)
            if match:
                receipt.update(checkout_sha=match[1].decode("ascii"), tree_sha=match[2].decode("ascii"))
        else:
            match = re.match(rb"systemd ([0-9]{1,10})(?=[ \n]|$)", data)
            if match:
                receipt["systemd_version"] = match[1].decode("ascii")
    try:
        receipt["kernel_release"] = os.uname().release
    except (OSError, AttributeError):
        pass
    if profile == "webkit":
        receipt.update(playwright_version="1.65.2", webkit_revision="2388")
        lock = "implementation/marketing/package-lock.json"
    else:
        lock = "implementation/desktop/Cargo.lock"
        try:
            import tomllib
            receipt["rust_channel"] = tomllib.loads(read_source_file("rust-toolchain.toml", 4096).decode("utf-8"))["toolchain"]["channel"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    try:
        receipt["lock_sha256"] = hashlib.sha256(read_source_file(lock, SOURCE_LOCK_LIMIT)).hexdigest()
    except (OSError, ValueError):
        pass
    return safe_source_receipt(receipt)


def safe_frame(frame):
    return {key: frame[key] for key in ("ordinal", "module", "offset", "symbol") if key in frame}


def encode_export(result):
    # Only these fields cross the public boundary. Absolute PCs, boot IDs and
    # canonical installed paths are private even when the stack was selected.
    payload = {key: result[key] for key in (
        "schema_version", "availability", "handler", "partial", "truncated",
        "rejected_records", "candidate_scan_complete", "export_truncated", "omission_reasons",
    )}
    if "installed_identity" in result:
        payload["installed_identity"] = result["installed_identity"]
    stage = result.get("kernel_rejection_stage")
    if stage in KERNEL_REJECTION_STAGES:
        payload["kernel_rejection_stage"] = stage
    if "source_receipt" in result:
        receipt = safe_source_receipt(result["source_receipt"])
        if receipt is not None:
            payload["source_receipt"] = receipt
    if result.get("_profile", "webkit") == "webkit" and "kernel_module_policy_observation" in result:
        observation = safe_module_observation(result["kernel_module_policy_observation"])
        if observation is None:
            payload["partial"] = True
        else:
            payload["kernel_module_policy_observation"] = observation
    records = payload["records"] = []

    def mark_export_limit():
        payload["truncated"] = payload["partial"] = payload["export_truncated"] = True
        payload["omission_reasons"] = sorted({*payload["omission_reasons"], "export_limit"})

    for record in result["records"]:
        safe = {key: record[key] for key in (
            "pid", "timestamp_us", "signal", "role", "partial", "core_truncated",
            "core_storage", "module_identity",
        )}
        fault = record["fault_attribution"]["fault_thread"]
        safe["fault_attribution"] = {"fault_thread": None}
        if fault is not None:
            safe["fault_attribution"]["fault_thread"] = {
                "tid": fault["tid"], "basis": FAULT_BASIS, "delta_us": fault["delta_us"],
                "frame_zero": safe_frame(fault["frame_zero"]),
            }
        if "executable" in record:
            safe["executable"] = record["executable"]
        threads = safe["threads"] = []
        ordered = record["threads"]
        if fault is not None:
            ordered = sorted(ordered, key=lambda t: (t["tid"] != fault["tid"], t["_listing_index"]))
        for thread in ordered[:STACK_EXPORT_LIMIT]:
            selected = fault is not None and thread["tid"] == fault["tid"]
            frames = thread["frames"]
            if selected:
                frames = sorted(frames, key=lambda f: f["ordinal"] != 0)
            threads.append({
                "tid": thread["tid"], "basis": FAULT_BASIS if selected else "listed_only",
                "frames": [safe_frame(f) for f in frames],
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
                stack = record["threads"][-1]
                if stack["basis"] == FAULT_BASIS:
                    break
                if stack["frames"]:
                    stack["frames"].pop()
                else:
                    record["threads"].pop()
                record["partial"] = True
                encoded = encode()
        # Fault context outranks listed peers. Always retain original #0.
        for record in records:
            if record["fault_attribution"]["fault_thread"] is not None:
                frames = record["threads"][0]["frames"]
                while len(frames) > 1 and len(encoded) + 1 > EXPORT_LIMIT:
                    frames.pop()
                    record["partial"] = True
                    encoded = encode()
        while records and len(encoded) + 1 > EXPORT_LIMIT:
            index = next((i for i in reversed(range(len(records)))
                          if records[i]["fault_attribution"]["fault_thread"] is None), -1)
            records.pop(index)
            encoded = encode()
    return encoded


def export(result):
    print(encode_export(result))


def encode_timeout(result):
    # Prepare a small receipt before expensive work can hit the deadline.
    # Keep only already collected crash headers. No attribution can survive
    # a timeout, and this does not traverse or re-encode any stacks.
    payload = summary("timeout", result["handler"])
    payload["truncated"] = True
    payload["omission_reasons"] = sorted({*result["omission_reasons"], "deadline", "join_incomplete"})
    for record in result["records"]:
        header = {key: record[key] for key in (
            "pid", "timestamp_us", "signal", "role", "core_truncated", "core_storage",
        )}
        if "executable" in record:
            header["executable"] = record["executable"]
        header.update(partial=True, threads=[], module_identity={},
                      fault_attribution={"fault_thread": None})
        payload["records"].append(header)
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


EMPTY_TIMEOUT_EXPORT = encode_timeout(summary())


def write_export(encoded, deadline):
    # Bypass buffered stdout so there is nothing for interpreter shutdown to
    # flush. A backpressured or broken sink can leave a partial/missing line.
    try:
        with time_bound(deadline):
            fd = sys.stdout.fileno()
            pending = memoryview((encoded + "\n").encode("ascii"))
            while pending:
                count = os.write(fd, pending)
                if count == 0:
                    break
                pending = pending[count:]
    except (DiagnosticDeadline, OSError, ValueError):
        pass


def mark_incomplete(result, *reasons):
    for record in result["records"]:
        record["fault_attribution"] = {"fault_thread": None}
    result["candidate_scan_complete"] = False
    result["partial"] = True
    result["omission_reasons"] = sorted({*result["omission_reasons"], *reasons, "join_incomplete"})


def attach_kernel(result, availability, kernel_data, cut, reaped, *, profile=None):
    reasons = set()
    if cut:
        reasons.add("deadline" if availability == "timeout" else "kernel_limit")
        # The final complete line may already be exactly on the byte cap.
        kernel_data = kernel_data[:kernel_data.rfind(b"\n") + 1]
    if availability == "timeout":
        reasons.add("deadline")
    elif availability != "available":
        reasons.add("kernel_unavailable")
        kernel_data = None
    if not reaped:
        reasons.add("reap_unconfirmed")
    records, complete, join_reasons = correlate_kernel(
        result["records"], kernel_data, result["candidate_scan_complete"] and not reasons,
        diagnostics=result, profile=result.get("_profile", "webkit") if profile is None else profile,
        observation_complete=not reasons and not bool(set(result["omission_reasons"]) & {"raw_limit", "deadline"}),
    )
    reasons |= join_reasons
    result["records"] = records
    result["candidate_scan_complete"] = complete
    result["partial"] |= bool(reasons - {"kernel_no_match"})
    result["truncated"] |= bool(reasons & {"kernel_limit", "deadline"})
    result["omission_reasons"] = sorted({*result["omission_reasons"], *reasons})


def main():
    start = time.monotonic()
    output_deadline = start + METADATA_SECONDS
    deadline = output_deadline - OUTPUT_RESERVE_SECONDS
    parser = PrivateParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--journal-jsonl", metavar="FILE")
    parser.add_argument("--kernel-jsonl", metavar="FILE")
    parser.add_argument("--candidate-source-sha")
    parser.add_argument("--profile", choices=("webkit", "gpu-parity"), default="webkit")
    try:
        options = parser.parse_args()
        if options.kernel_jsonl is not None and options.journal_jsonl is None:
            raise ValueError
        since, until = number(options.since, 12), number(options.until, 12)
        # journalctl must be able to represent both times in ordinary UTC.
        if since > until or until - since >= WINDOW_SECONDS or until > MAX_EPOCH_SECONDS:
            raise ValueError
    except ValueError:
        invalid = json.dumps(summary("invalid_window"), separators=(",", ":"), ensure_ascii=True)
        write_export(invalid, output_deadline)
        return 2

    fallback = EMPTY_TIMEOUT_EXPORT
    offline = options.journal_jsonl is not None
    handler = "not_checked"
    result = summary()
    availability, reaped, crash_population_complete = "unavailable", True, False
    try:
        if offline:
            with time_bound(deadline):
                availability, data, cut = replay(options.journal_jsonl)
            reaped = True
        else:
            with time_bound(deadline):
                handler = core_handler()
            availability, data, cut, reaped = query(since, until, deadline)
        result = summary(availability, handler)
        result["_profile"] = options.profile
        with time_bound(deadline):
            if availability in ("available", "timeout"):
                collect(result, data, cut, since, until, profile=options.profile)
            crash_population_complete = result.get("_record_population_complete", False)
            if availability == "timeout":
                mark_incomplete(result, "deadline")
            if not reaped:
                mark_incomplete(result, "reap_unconfirmed")
            fallback = encode_timeout(result)
        # Coredump-only replay remains useful for legacy non-segfault inputs.
        # A SIGSEGV without a companion never counts as a completed join.
        need_kernel = (
            options.kernel_jsonl is not None
            or not offline and availability == "available"
            or any(record["signal"] == "SIGSEGV" for record in result["records"])
        )
        if need_kernel:
            if options.kernel_jsonl is not None:
                try:
                    with time_bound(deadline):
                        kernel_status = (*replay(options.kernel_jsonl, KERNEL_LIMIT), True)
                except (OSError, ValueError):
                    kernel_status = ("unavailable", b"", False, True)
            elif not offline and availability == "available":
                kernel_status = query_kernel(since, until, deadline)
            else:
                kernel_status = ("unavailable", b"", False, True)
            with time_bound(deadline):
                attach_kernel(result, *kernel_status, profile=options.profile)
                fallback = encode_timeout(result)
        with time_bound(deadline):
            if not offline:
                result["source_receipt"] = source_receipt(
                    options.profile, options.candidate_source_sha, deadline=deadline,
                )
            encoded = encode_export(result)
    except DiagnosticDeadline:
        write_export(fallback, output_deadline)
        return 0
    except (OSError, subprocess.SubprocessError, ValueError):
        result = summary(handler=handler)
        try:
            with time_bound(deadline):
                encoded = json.dumps(result, separators=(",", ":"), ensure_ascii=True)
        except DiagnosticDeadline:
            write_export(fallback, output_deadline)
            return 0

    if not offline:
        # If coredump inspection may have missed another parity executable,
        # the admitted records do not establish a unique crash.
        identities = result["records"]
        if options.profile == "gpu-parity" and (
            availability != "available" or not reaped or not crash_population_complete
        ):
            identities = []
        identity_start = time.monotonic()
        private_identity = {}
        identity, reasons = installed_identity(
            options.profile, identities,
            deadline=output_deadline + IDENTITY_SECONDS - OUTPUT_RESERVE_SECONDS,
            private_observation=private_identity,
        )
        # Only time spent in the separate identity phase extends the hard
        # deadline. Metadata and final output share the original budget.
        output_deadline += min(IDENTITY_SECONDS, time.monotonic() - identity_start)
        if identity is not None or reasons or "_module_rejections" in result:
            try:
                with time_bound(output_deadline - OUTPUT_RESERVE_SECONDS):
                    if options.profile == "webkit" and "_module_rejections" in result:
                        result["kernel_module_policy_observation"] = _finalize_module_rejections(
                            result["_module_rejections"], private_identity.get("_resolved_basename"),
                        )
                    if identity is not None:
                        result["installed_identity"] = identity
                    if reasons:
                        result["partial"] = True
                        result["omission_reasons"] = sorted({*result["omission_reasons"], *reasons})
                    encoded = encode_export(result)
            except DiagnosticDeadline:
                encoded = fallback
    write_export(encoded, output_deadline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
