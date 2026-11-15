"""Isolated child process with an absolute deadline across both pipes."""
import base64
import binascii
import json
import os
import selectors
import signal
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic

from ..configuration import valid_id
from ..contracts import ProvisioningCredential
from .transport_child import INPUT_MAX, READ_MAX, WRITE_MAX, loads

_CHILD = Path(__file__).resolve().with_name("transport_child.py")
_MAX_FRAME = 6 * 1024 * 1024
_CODES = frozenset({
    "VALIDATION", "SPAWN_FAILURE", "INPUT_PROTOCOL", "CONNECT_TIMEOUT", "READ_TIMEOUT", "ABSOLUTE_TIMEOUT",
    "RESPONSE_TOO_LARGE", "RESPONSE_PROTOCOL", "TRANSPORT_FAILURE",
})


@dataclass(frozen=True, slots=True)
class _Operation:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    body: dict | None = None


@dataclass(frozen=True, slots=True)
class _Failure:
    phase: str
    code: str


@dataclass(frozen=True, slots=True)
class _Response:
    status: int
    request_id: str | None
    body: bytes = field(repr=False)


def _decode_response(data, maximum):
    value = loads(data)
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError
    if value.get("kind") == "failure":
        if (
            value.keys() != {"schema_version", "kind", "phase", "code"}
            or value["phase"] not in ("before_http", "possible_dispatch") or value["code"] not in _CODES
        ):
            raise ValueError
        return _Failure(value["phase"], value["code"])
    if (
        value.get("kind") != "response"
        or value.keys() != {"schema_version", "kind", "status", "request_id", "body_b64"}
        or type(value["status"]) is not int or not 100 <= value["status"] <= 599
        or (value["request_id"] is not None and not valid_id(value["request_id"]))
        or type(value["body_b64"]) is not str
    ):
        raise ValueError
    body = base64.b64decode(value["body_b64"], validate=True)
    if len(body) > maximum or base64.b64encode(body).decode() != value["body_b64"]:
        raise ValueError
    return _Response(value["status"], value["request_id"], body)


def _kill_and_wait(proc, end):
    # A validated frame is self-delimiting. Reap the process group even if
    # a child emits a complete frame and then stalls before closing its pipes.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        os._exit(78)
    for pipe in (proc.stdin, proc.stdout):
        if not pipe.closed:
            pipe.close()
    try:
        proc.wait(timeout=max(0, end - monotonic()))
    except subprocess.TimeoutExpired:
        os._exit(78)


def _roundtrip(proc, frame, end):
    received = bytearray()
    offset = 0
    expected = None
    with selectors.DefaultSelector() as selector:
        for pipe, event in ((proc.stdin, selectors.EVENT_WRITE), (proc.stdout, selectors.EVENT_READ)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, event)
        while (remaining := end - monotonic()) > 0:
            for key, event in selector.select(remaining):
                if event == selectors.EVENT_WRITE:
                    try:
                        offset += os.write(key.fd, memoryview(frame)[offset:])
                    except BrokenPipeError:
                        return _Failure("possible_dispatch", "INPUT_PROTOCOL")
                    except BlockingIOError:
                        continue
                    if offset == len(frame):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    try:
                        piece = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not piece:
                        return _Failure("possible_dispatch", "RESPONSE_PROTOCOL")
                    received.extend(piece)
                    if expected is None and len(received) >= 4:
                        expected = struct.unpack("!I", received[:4])[0]
                        if not 0 < expected <= _MAX_FRAME:
                            return _Failure("possible_dispatch", "RESPONSE_TOO_LARGE")
                    if expected is not None and len(received) >= 4 + expected:
                        if len(received) != expected + 4 or offset != len(frame):
                            return _Failure("possible_dispatch", "RESPONSE_PROTOCOL")
                        return received[4:]
    return _Failure("possible_dispatch", "ABSOLUTE_TIMEOUT")


def _send(operation: _Operation, credential: ProvisioningCredential) -> _Response | _Failure:
    from ..capacity import close_database

    started = monotonic()
    if os.name != "posix" or not hasattr(signal, "setitimer"):
        return _Failure("before_http", "SPAWN_FAILURE")
    close_database()
    raw = json.dumps({
        "schema_version": 1, "provider": credential.scope.provider, "parent_scope_id": credential.scope.parent_scope_id,
        "method": operation.method, "path": operation.path, "query": operation.query, "body": operation.body,
        "credential_b64": base64.b64encode(credential.secret.value).decode("ascii"), "absolute_timeout_ms": 9000,
    }, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    if len(raw) > INPUT_MAX:
        return _Failure("before_http", "VALIDATION")
    frame = struct.pack("!I", len(raw)) + raw
    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", str(_CHILD)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, close_fds=True, shell=False, start_new_session=True, bufsize=0,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except OSError:
        return _Failure("before_http", "SPAWN_FAILURE")
    try:
        answer = _roundtrip(proc, frame, started + 9)
        if isinstance(answer, _Failure):
            return answer
        return _decode_response(answer, READ_MAX if operation.method == "GET" else WRITE_MAX)
    except (OSError, ValueError, TypeError, binascii.Error):
        return _Failure("possible_dispatch", "RESPONSE_PROTOCOL")
    finally:
        _kill_and_wait(proc, started + 10)
