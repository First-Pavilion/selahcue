"""Deadline-bound transport for one isolated grant subprocess."""
import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime
import os
from pathlib import Path
import selectors
import signal
import struct
import subprocess
import sys
import time

from selahcue_api.apps.providers.contracts import MintFailureCode as Code
from selahcue_api.apps.usage.weeks import utc_instant

from .grants_child import (
    FAILURE_CODES, MAX_CONTROL, MAX_FINAL, MAX_PREPARE, MAX_RESPONSE, decode_base64, frame, parse_frame,
)

_CHILD = Path(__file__).with_name("grants_child.py").resolve()
_MIN_CHILD_NS = 500_000_000
_READY = {"schema_version": 1, "kind": "ready"}


@dataclass(frozen=True, slots=True)
class TransportReply:
    status: int
    body: bytes = field(repr=False)
    response_received_at: datetime


@dataclass(frozen=True, slots=True)
class TransportFailure:
    code: Code
    before_http: bool


def _possible_send(dispatch):
    authorization = dispatch.authorization
    now = time.monotonic_ns()
    return (
        now < min(authorization.send_not_after_ns, dispatch.io_deadline_ns)
        and datetime.now(UTC) < authorization.send_not_after_utc
    )


def _await(pipe, mode, deadline):
    remaining = (deadline - time.monotonic_ns()) / 1_000_000_000
    if remaining <= 0:
        raise TimeoutError
    with selectors.DefaultSelector() as selector:
        selector.register(pipe, mode)
        if not selector.select(remaining):
            raise TimeoutError


def _write(pipe, data, deadline):
    pos = 0
    while pos < len(data):
        _await(pipe, selectors.EVENT_WRITE, deadline)
        try:
            pos += os.write(pipe.fileno(), data[pos:])
        except BlockingIOError:
            continue


def _read(pipe, count, deadline):
    result = bytearray()
    while len(result) < count:
        _await(pipe, selectors.EVENT_READ, deadline)
        try:
            part = os.read(pipe.fileno(), count - len(result))
        except BlockingIOError:
            continue
        if not part:
            raise EOFError
        result.extend(part)
    return bytes(result)


def _read_frame(pipe, limit, deadline):
    size, = struct.unpack(">I", _read(pipe, 4, deadline))
    if not 0 < size <= limit:
        raise ValueError("Invalid child frame length")
    return parse_frame(_read(pipe, size, deadline))


def _read_end(pipe, deadline):
    while True:
        _await(pipe, selectors.EVENT_READ, deadline)
        try:
            if os.read(pipe.fileno(), 1):
                raise ValueError("Unexpected trailing child bytes")
            return
        except BlockingIOError:
            continue


def _final_frame(fields):
    kind = fields.get("kind")
    if kind == "failure" and set(fields) == {"schema_version", "kind", "phase", "code"}:
        phase, code = fields["phase"], fields["code"]
        if phase not in ("before_http", "possible_dispatch") or type(code) is not str or code not in FAILURE_CODES:
            raise ValueError("Invalid child failure")
        if phase == "before_http":
            return TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)
        failure = Code.TRANSPORT_TIMEOUT if code in {
            "CONNECT_TIMEOUT", "READ_TIMEOUT", "ABSOLUTE_TIMEOUT",
        } else Code.TRANSPORT_ERROR
        return TransportFailure(failure, False)
    if kind == "response" and set(fields) == {"schema_version", "kind", "status", "body_b64"}:
        status = fields["status"]
        if type(status) is not int or not 100 <= status <= 599:
            raise ValueError("Invalid response status")
        body = decode_base64(fields["body_b64"], MAX_RESPONSE)
        return TransportReply(status, body, datetime.now(UTC))
    raise ValueError("Unexpected child frame")


def _cleanup(process, deadline, *, kill):
    if kill and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            # Reap still has the same deadline, including when the group has
            # exited between poll and signal.
            pass
    process.stdin.close()
    process.stdout.close()
    try:
        return process.wait(timeout=max(0, (deadline - time.monotonic_ns()) / 1_000_000_000))
    except subprocess.TimeoutExpired:
        # Reap is a security boundary. The supervisor replaces this worker.
        os._exit(78)


def run_grant_transport(dispatch) -> TransportReply | TransportFailure:
    authorization = dispatch.authorization
    secret = authorization.secret.value
    if (
        os.name != "posix" or not 0 < len(secret) <= 4096
        or any(not 33 <= byte <= 126 for byte in secret)
        or not _possible_send(dispatch)
        or dispatch.io_deadline_ns - time.monotonic_ns() < _MIN_CHILD_NS
    ):
        return TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)
    prepare = frame({
        "kind": "prepare",
        "credential_b64": base64.b64encode(secret).decode("ascii"),
        "send_not_after_ns": authorization.send_not_after_ns,
        "io_deadline_ns": dispatch.io_deadline_ns,
        "send_not_after_utc": utc_instant(authorization.send_not_after_utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
    })
    if len(prepare) - 4 > MAX_PREPARE or not _possible_send(dispatch):
        return TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", str(_CHILD)], shell=False, close_fds=True, start_new_session=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"}, bufsize=0,
        )
    except OSError:
        return TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)
    possible_dispatch = False
    complete = False
    io = dispatch.io_deadline_ns
    result = TransportFailure(Code.TRANSPORT_ERROR, True)
    try:
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        if not _possible_send(dispatch):
            return TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)
        _write(process.stdin, prepare, io)
        first = _read_frame(process.stdout, MAX_CONTROL, io)
        if first != _READY:
            refusal = _final_frame(first)
            if not isinstance(refusal, TransportFailure) or not refusal.before_http:
                raise ValueError("Unexpected response before GO")
            result = refusal
        elif _possible_send(dispatch):
            # A partial/failed GO write is unproven once it begins.
            possible_dispatch = True
            _write(process.stdin, frame({"kind": "go"}), io)
            result = _final_frame(_read_frame(process.stdout, MAX_FINAL, io))
        else:
            return TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)
        _read_end(process.stdout, io)
        complete = True
    except TimeoutError:
        result = TransportFailure(Code.TRANSPORT_TIMEOUT, not possible_dispatch)
    except (ValueError, TypeError, EOFError, OSError, RecursionError):
        result = TransportFailure(Code.TRANSPORT_ERROR, not possible_dispatch)
    finally:
        status = _cleanup(process, dispatch.overall_deadline_ns, kill=not complete)
    if time.monotonic_ns() >= dispatch.overall_deadline_ns:
        return TransportFailure(Code.TRANSPORT_TIMEOUT, not possible_dispatch)
    if not complete and status == -signal.SIGALRM:
        return TransportFailure(Code.TRANSPORT_TIMEOUT, not possible_dispatch)
    if complete and status:
        return TransportFailure(Code.TRANSPORT_ERROR, not possible_dispatch)
    return result
