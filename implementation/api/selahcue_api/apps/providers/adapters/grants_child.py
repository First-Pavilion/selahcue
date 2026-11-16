"""Isolated one-shot fixed-destination grant subprocess. Standard library only."""
import base64
import binascii
from datetime import UTC, datetime
import http.client
import json
import re
import resource
import signal
import socket
import ssl
import struct
import sys
import time
from urllib.parse import urlsplit

_MINT_URL = "https://api.deepgram.com/v1/auth/grant"
_MINT_TARGET = urlsplit(_MINT_URL)
MAX_PREPARE = 8192
MAX_CONTROL = 128
MAX_FINAL = 24576
MAX_RESPONSE = 16384
PREPARE_FIELDS = frozenset({
    "schema_version", "kind", "credential_b64", "send_not_after_ns", "io_deadline_ns", "send_not_after_utc",
})
FAILURE_CODES = frozenset({
    "VALIDATION", "INPUT_PROTOCOL", "CONNECT_TIMEOUT", "READ_TIMEOUT", "ABSOLUTE_TIMEOUT",
    "RESPONSE_TOO_LARGE", "RESPONSE_PROTOCOL", "TRANSPORT_FAILURE",
})


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate object key")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("Nonfinite value")


def strict_object(data, **kwargs):
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite, **kwargs)
    if type(value) is not dict:
        raise ValueError("Expected object")
    return value


def decode_base64(raw, maximum):
    if type(raw) is not str or len(raw) > (maximum + 2) // 3 * 4:
        raise ValueError("Invalid base64")
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Invalid base64") from None
    if len(decoded) > maximum or base64.b64encode(decoded).decode("ascii") != raw:
        raise ValueError("Invalid base64")
    return decoded


def frame(fields):
    raw = json.dumps({"schema_version": 1, **fields}, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


def parse_frame(raw):
    fields = strict_object(raw)
    if type(fields.get("schema_version")) is not int or fields["schema_version"] != 1:
        raise ValueError("Invalid frame version")
    return fields


def _read_frame(limit):
    data = sys.stdin.buffer.read(4)
    if len(data) != 4:
        raise ValueError("Incomplete header")
    length, = struct.unpack(">I", data)
    if not 0 < length <= limit:
        raise ValueError("Invalid frame length")
    data = sys.stdin.buffer.read(length)
    if len(data) != length:
        raise ValueError("Incomplete frame")
    return parse_frame(data)


def _emit(fields):
    sys.stdout.buffer.write(frame(fields))
    sys.stdout.buffer.flush()


def _failure(phase, code):
    _emit({"kind": "failure", "phase": phase, "code": code})


def _prepare(input_frame):
    if set(input_frame) != PREPARE_FIELDS or input_frame["kind"] != "prepare":
        raise ValueError("Invalid preparation frame")
    credential = decode_base64(input_frame["credential_b64"], 4096)
    if not credential or any(not 33 <= byte <= 126 for byte in credential):
        raise ValueError("Invalid credential")
    send, io = (input_frame[name] for name in ("send_not_after_ns", "io_deadline_ns"))
    if any(type(value) is not int or value <= 0 for value in (send, io)):
        raise ValueError("Invalid monotonic deadline")
    raw_at = input_frame["send_not_after_utc"]
    if type(raw_at) is not str or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", raw_at,
    ) is None:
        raise ValueError("Invalid UTC deadline")
    return credential.decode("ascii"), send, io, datetime.fromisoformat(raw_at)


def _inside_horizon(send, io, at):
    now = time.monotonic_ns()
    return now < send and now < io and datetime.now(UTC) < at


def _socket_timeout(io):
    remaining = (io - time.monotonic_ns()) / 1_000_000_000
    if remaining <= 0:
        raise TimeoutError
    return min(2, remaining)


def _run():
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, 3.5)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        credential, send, io, at = _prepare(_read_frame(MAX_PREPARE))
        remaining = min(signal.getitimer(signal.ITIMER_REAL)[0], (io - time.monotonic_ns()) / 1_000_000_000)
        if remaining <= 0 or not _inside_horizon(send, io, at):
            return _failure("before_http", "ABSOLUTE_TIMEOUT")
        signal.setitimer(signal.ITIMER_REAL, remaining)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return _failure("before_http", "INPUT_PROTOCOL")

    _emit({"kind": "ready"})
    try:
        if _read_frame(MAX_CONTROL) != {"schema_version": 1, "kind": "go"}:
            return _failure("before_http", "INPUT_PROTOCOL")
    except (ValueError, TypeError, RecursionError):
        return _failure("before_http", "INPUT_PROTOCOL")
    if not _inside_horizon(send, io, at):
        return _failure("before_http", "ABSOLUTE_TIMEOUT")

    phase = "before_http"
    connection = None
    try:
        connection = http.client.HTTPSConnection(
            _MINT_TARGET.hostname, timeout=_socket_timeout(io), context=ssl.create_default_context(),
        )
        connection.connect()
        connection.sock.settimeout(_socket_timeout(io))
        headers = {"Authorization": f"Token {credential}", "Content-Type": "application/json"}
        if not _inside_horizon(send, io, at):
            return _failure(phase, "ABSOLUTE_TIMEOUT")
        phase = "possible_dispatch"
        connection.request("POST", _MINT_TARGET.path, body=b'{"ttl_seconds":30}', headers=headers)
        connection.sock.settimeout(_socket_timeout(io))
        # HTTPConnection may relinquish its socket reference at getresponse() when
        # the peer ends keep-alive. Retain the same socket for bounded chunk reads.
        wire_socket = connection.sock
        with connection.getresponse() as response:
            if response.length is not None and response.length > MAX_RESPONSE:
                return _failure(phase, "RESPONSE_TOO_LARGE")
            expected = response.length
            body = bytearray()
            while len(body) <= MAX_RESPONSE and not response.isclosed():
                wire_socket.settimeout(_socket_timeout(io))
                chunk = response.read(min(4096, MAX_RESPONSE + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
            if len(body) > MAX_RESPONSE:
                return _failure(phase, "RESPONSE_TOO_LARGE")
            if expected is not None and len(body) != expected:
                return _failure(phase, "RESPONSE_PROTOCOL")
            _emit({"kind": "response", "status": response.status, "body_b64": base64.b64encode(body).decode("ascii")})
    except (TimeoutError, socket.timeout):
        return _failure(phase, "CONNECT_TIMEOUT" if phase == "before_http" else "READ_TIMEOUT")
    except http.client.HTTPException:
        return _failure(phase, "RESPONSE_PROTOCOL")
    except (OSError, ValueError):
        return _failure(phase, "TRANSPORT_FAILURE")
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    _run()
