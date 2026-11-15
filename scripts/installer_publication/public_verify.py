"""Bounded public installer downloads, independent of the authenticated supplier."""

from collections.abc import Callable
import hashlib
import os
from pathlib import Path
import re
import selectors
import socket
import ssl
import subprocess
import sys
import threading
import time
from typing import Protocol, Self

from .contracts import (
    MAX_JSON_BYTES,
    MAX_STRING_BYTES,
    PUBLIC_ORIGIN,
    ObjectPlan,
    PublicationError,
    PublicPlan,
    ResponseHeaders,
    VerificationReceipt,
    VerifiedObject,
    headers_match,
    parse_object_plan,
    parse_public_plan,
    parse_verified_object,
    record_bytes,
    utc_now,
)

_HOST = PUBLIC_ORIGIN.removeprefix("https://")
_CONNECT_TIMEOUT = 30.0
_IDLE_TIMEOUT = 60.0
_TOTAL_TIMEOUT = 3600.0
_CHUNK = 1024 * 1024
_HEADER_LIMIT = 64 * 1024
_MAX_ATTEMPTS = 3

_STATUS = re.compile(rb"HTTP/1\.[01] ([1-5][0-9]{2}) [\x20-\x7e]*\r\n")
_FIELD_NAME = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_FIELD_VALUE = re.compile(rb"[\t\x20-\x7e\x80-\xff]*")
_LENGTH = re.compile(r"[1-9][0-9]{0,9}")
_ERROR_DOCUMENT = re.compile(rb"(?i)<(?:!doctype\s+html\b|html\b|\?xml\b|error(?:response)?\b)")
_OBSERVED = frozenset({b"content-length", b"content-type", b"content-disposition", b"cache-control"})
_FORBIDDEN = frozenset({
    b"transfer-encoding", b"content-encoding", b"content-range", b"www-authenticate", b"proxy-authenticate",
})
_CREDENTIAL_NAMES = frozenset({
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY", "AWS_SECRET_KEY", "AWS_CREDENTIAL_FILE",
    "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN", "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_CONFIG_FILE",
    "AWS_SHARED_CREDENTIALS_FILE", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN", "BOTO_CONFIG",
    "GOOGLE_APPLICATION_CREDENTIALS", "AZURE_CLIENT_SECRET", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
})
_CREDENTIAL_SUFFIXES = (
    "_ACCESS_KEY", "_ACCESS_KEY_ID", "_SECRET_KEY", "_API_KEY", "_TOKEN", "_CREDENTIALS_FILE",
)


class _Connection(Protocol):
    def __enter__(self) -> Self: ...
    def __exit__(self, *error: object) -> None: ...
    def settimeout(self, seconds: float) -> None: ...
    def sendall(self, request: bytes) -> None: ...
    def recv(self, size: int) -> bytes: ...


_Clock = Callable[[], float]
_Connector = Callable[[float, _Clock], _Connection]


def _credential_free() -> None:
    for name in os.environ:
        upper = name.upper()
        if (upper in _CREDENTIAL_NAMES or upper.endswith(_CREDENTIAL_SUFFIXES)
                or upper.startswith(("INSTALLER_S3_", "AWS_CONTAINER_"))):
            raise PublicationError(3, "verify-public requires a credential-free environment")


def _remaining(deadline: float, clock: _Clock) -> float:
    seconds = deadline - clock()
    if seconds <= 0:
        raise TimeoutError
    return seconds


def _resolve(deadline: float, clock: _Clock) -> list[tuple]:
    # getaddrinfo has no socket timeout. A stalled resolver must not stall the
    # verifier; its daemon thread cannot keep the command alive after failure.
    finished = threading.Event()
    addresses = []

    def lookup() -> None:
        try:
            addresses.extend(socket.getaddrinfo(_HOST, 443, type=socket.SOCK_STREAM))
        except OSError:
            pass
        finally:
            finished.set()

    threading.Thread(target=lookup, daemon=True).start()
    if not finished.wait(_remaining(deadline, clock)):
        raise TimeoutError
    if not addresses:
        raise OSError
    return addresses


def _connect_https(deadline: float, clock: _Clock) -> ssl.SSLSocket:
    addresses = _resolve(deadline, clock)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    for family, kind, protocol, _, address in addresses:
        connection = socket.socket(family, kind, protocol)
        try:
            connection.settimeout(_remaining(deadline, clock))
            connection.connect(address)
            connection.settimeout(_remaining(deadline, clock))
            return context.wrap_socket(connection, server_hostname=_HOST, suppress_ragged_eofs=False)
        except ssl.SSLCertVerificationError:
            connection.close()
            raise
        except OSError:
            connection.close()
    raise OSError


def _error(obj: ObjectPlan, code: int, reason: str) -> PublicationError:
    return PublicationError(code, f"verify-public {obj.id}: {reason}")


class _Response:
    def __init__(self, obj: ObjectPlan, connection: _Connection, deadline: float, clock: _Clock):
        self.obj = obj
        self.connection = connection
        self.deadline = deadline
        self.clock = clock
        self.header_budget = _HEADER_LIMIT

    def _timeout(self) -> None:
        self.connection.settimeout(min(_IDLE_TIMEOUT, _remaining(self.deadline, self.clock)))

    def _read(self, size: int) -> bytes:
        self._timeout()
        data = self.connection.recv(size)
        _remaining(self.deadline, self.clock)
        return data

    def _line(self) -> bytes:
        # Keep the socket unbuffered to avoid reading body bytes ahead of the
        # exact length+one-byte allowance, even for a very small package.
        line = bytearray()
        while self.header_budget:
            byte = self._read(1)
            if not byte:
                if not line and self.header_budget == _HEADER_LIMIT:
                    raise OSError  # The peer closed before producing a response.
                break
            self.header_budget -= 1
            line.extend(byte)
            if byte == b"\n":
                return bytes(line)
        raise _error(self.obj, 3, "Incomplete or oversized HTTP headers")

    def _headers(self) -> ResponseHeaders:
        status_line = _STATUS.fullmatch(self._line())
        if not status_line:
            raise _error(self.obj, 3, "Invalid HTTP status")
        status = int(status_line[1])
        if status in (408, 429) or status >= 500:
            raise _error(self.obj, 4, "Transient HTTP response")
        if status != 200:
            raise _error(self.obj, 3, "Expected HTTP 200")
        values: dict[bytes, str] = {}
        while (line := self._line()) != b"\r\n":
            name, separator, raw = line[:-2].partition(b":")
            if (not line.endswith(b"\r\n") or not separator
                    or not _FIELD_NAME.fullmatch(name) or not _FIELD_VALUE.fullmatch(raw)):
                raise _error(self.obj, 3, "Malformed response header")
            name = name.lower()
            if name in _FORBIDDEN:
                raise _error(self.obj, 3, "Forbidden response framing or authorization header")
            if name in _OBSERVED:
                value = raw.strip(b" \t")
                if (name in values or len(value) > MAX_STRING_BYTES
                        or not value or any(byte < 32 or byte > 126 for byte in value)):
                    raise _error(self.obj, 3, "Invalid or duplicate installer header")
                values[name] = value.decode("ascii")

        length = values.get(b"content-length", "")
        if not _LENGTH.fullmatch(length) or int(length) != self.obj.size_bytes:
            raise _error(self.obj, 3, "Content-Length differs from the object plan")
        headers = ResponseHeaders(
            values.get(b"content-type", ""),
            values.get(b"content-disposition", ""),
            values.get(b"cache-control", ""),
            int(length),
            None,
        )
        if not headers_match(headers, self.obj):
            raise _error(self.obj, 3, "Response headers differ from the object plan")
        return headers

    def download(self) -> VerifiedObject:
        obj = self.obj
        path = obj.url[len(PUBLIC_ORIGIN):]
        request = f"GET {path} HTTP/1.1\r\nHost: {_HOST}\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"
        self._timeout()
        self.connection.sendall(request.encode("ascii"))
        headers = self._headers()

        observed = 0
        digest = hashlib.sha256()
        prefix = bytearray()
        while data := self._read(min(_CHUNK, obj.size_bytes + 1 - observed)):
            observed += len(data)
            if observed > obj.size_bytes:
                raise _error(obj, 3, "Response exceeds Content-Length")
            prefix.extend(data[:512 - len(prefix)])
            digest.update(data)
        checksum = digest.hexdigest()
        if observed != obj.size_bytes or checksum != obj.sha256:
            raise _error(obj, 3, "Response bytes differ from the object plan")
        if _ERROR_DOCUMENT.match(bytes(prefix).removeprefix(b"\xef\xbb\xbf").lstrip()):
            raise _error(obj, 3, "Response is an HTML or XML document")
        return VerifiedObject(obj.id, obj.url, 200, headers, observed, checksum, utc_now())


def _verify_object(obj: ObjectPlan, connector: _Connector, clock: _Clock) -> VerifiedObject:
    obj = parse_object_plan(record_bytes(obj))
    deadline = clock() + _TOTAL_TIMEOUT
    for _ in range(_MAX_ATTEMPTS):
        try:
            connect_deadline = min(deadline, clock() + _CONNECT_TIMEOUT)
            _remaining(connect_deadline, clock)
            with connector(connect_deadline, clock) as connection:
                _remaining(connect_deadline, clock)
                return _Response(obj, connection, deadline, clock).download()
        except PublicationError as exc:
            if exc.exit_code != 4:
                raise
        except ssl.SSLCertVerificationError:
            raise _error(obj, 3, "TLS certificate verification failed") from None
        except OSError:
            pass
        if clock() >= deadline:
            break
    raise _error(obj, 4, "Anonymous readback timed out or exhausted its attempts")


def verify_object(obj: ObjectPlan) -> VerifiedObject:
    _credential_free()
    return _verify_object(obj, _connect_https, time.monotonic)


def verify_public_plan(plan: PublicPlan) -> VerificationReceipt:
    from .prepare import publisher_source_sha256

    _credential_free()
    raw = record_bytes(plan)
    plan = parse_public_plan(raw)
    source_digest = publisher_source_sha256()
    started = utc_now()
    objects = tuple(verify_object(obj) for obj in plan.objects)
    return VerificationReceipt(
        1, hashlib.sha256(raw).hexdigest(), f"installer-publication/1 sha256:{source_digest}",
        started, utc_now(), objects,
    )


def _child_argv() -> list[str]:
    scripts = str(Path(__file__).resolve().parents[1])
    program = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from installer_publication.public_verify import worker_main; "
        "raise SystemExit(worker_main())"
    )
    return [sys.executable, "-I", "-S", "-B", "-c", program, scripts]


def _exchange(child: subprocess.Popen, raw: bytes, deadline: float) -> bytes:
    incoming, outgoing = child.stdin, child.stdout
    assert incoming is not None and outgoing is not None
    pending = memoryview(raw)
    output = bytearray()
    with selectors.DefaultSelector() as selector:
        os.set_blocking(incoming.fileno(), False)
        os.set_blocking(outgoing.fileno(), False)
        selector.register(incoming, selectors.EVENT_WRITE)
        selector.register(outgoing, selectors.EVENT_READ)
        while selector.get_map():
            for key, _ in selector.select(_remaining(deadline, time.monotonic)):
                _remaining(deadline, time.monotonic)
                if key.fileobj is incoming:
                    try:
                        pending = pending[os.write(incoming.fileno(), pending):]
                    except BrokenPipeError:
                        pending = pending[len(pending):]
                    if not pending:
                        selector.unregister(incoming)
                        incoming.close()
                else:
                    chunk = os.read(outgoing.fileno(), min(65536, MAX_JSON_BYTES + 1 - len(output)))
                    if not chunk:
                        selector.unregister(outgoing)
                        continue
                    output.extend(chunk)
                    if len(output) > MAX_JSON_BYTES:
                        raise PublicationError(5, "Verifier child response exceeds its byte limit")
    return bytes(output)


def verify_object_in_child(obj: ObjectPlan) -> VerifiedObject:
    raw = record_bytes(obj)
    obj = parse_object_plan(raw)
    deadline = time.monotonic() + _TOTAL_TIMEOUT
    try:
        with subprocess.Popen(
            _child_argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env={},
        ) as child:
            try:
                output = _exchange(child, raw, deadline)
                status = child.wait(timeout=_remaining(deadline, time.monotonic))
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
    except (TimeoutError, subprocess.TimeoutExpired):
        raise _error(obj, 4, "Verifier child exceeded its deadline") from None
    except (OSError, ValueError, PublicationError):
        raise _error(obj, 5, "Verifier child protocol failed") from None
    if status in (3, 4) and not output:
        raise _error(obj, status, "Verifier child could not verify the object")
    if status != 0:
        raise _error(obj, 5, "Verifier child did not complete its protocol")
    try:
        result = parse_verified_object(output)
    except PublicationError:
        raise _error(obj, 5, "Invalid verifier child response") from None
    if (record_bytes(result) != output or result.id != obj.id or result.url != obj.url
            or result.observed_size_bytes != obj.size_bytes or result.observed_sha256 != obj.sha256
            or not headers_match(result.headers, obj)):
        raise _error(obj, 5, "Verifier child response differs from the object plan")
    return result


def worker_main() -> int:
    try:
        _credential_free()
        obj = parse_object_plan(sys.stdin.buffer.read(MAX_JSON_BYTES + 1))
        verified = verify_object(obj)
        sys.stdout.buffer.write(record_bytes(verified))
        sys.stdout.buffer.flush()
    except PublicationError as exc:
        return exc.exit_code
    except OSError:
        return 5
    return 0
