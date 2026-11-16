"""Isolated stdlib-only transport for the two fixed provider usage profiles."""
import base64
import http.client
import json
import re
import resource
import signal
import ssl
import struct
import sys
import time
from datetime import UTC, datetime
from urllib.parse import quote, urlencode

MAX_INPUT = 32_768
MAX_OUTPUT = 1_500_000
MAX_BODY = 1_048_576
_FIELDS = {
    "schema_version", "provider", "parent_scope_id", "profile", "start_time",
    "end_time", "cursor", "credential_b64", "io_deadline_ns",
}


def frame(value):
    data = json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    return struct.pack("!I", len(data)) + data


def decode_b64(text, limit):
    if type(text) is not str or len(text) > ((limit + 2) // 3) * 4:
        raise ValueError
    result = base64.b64decode(text, validate=True)
    if len(result) > limit or base64.b64encode(result).decode("ascii") != text:
        raise ValueError
    return result


def valid_cursor(cursor):
    return (
        type(cursor) is str and 1 <= len(cursor.encode("utf-8", errors="strict")) <= 4096
        and all(ord(char) >= 32 and not 127 <= ord(char) <= 159 for char in cursor)
    )


def dg_page(cursor):
    if cursor is None:
        return 0
    if type(cursor) is not str or not re.fullmatch(r"0|[1-9][0-9]{0,18}", cursor):
        raise ValueError
    parsed = int(cursor)
    if parsed >= 2**63:
        raise ValueError
    return parsed


def _seconds(stamp):
    if type(stamp) is not int or not -62135596800 <= stamp <= 253402300799:
        raise ValueError
    return datetime.fromtimestamp(stamp, UTC)


def invocation(data):
    if type(data) is not dict or set(data) != _FIELDS or type(data["schema_version"]) is not int:
        raise ValueError
    if data["schema_version"] != 1 or type(data["io_deadline_ns"]) is not int:
        raise ValueError
    parent = data["parent_scope_id"]
    if type(parent) is not str or not re.fullmatch(r"[\x21-\x7e]{1,256}", parent):
        raise ValueError
    credential = decode_b64(data["credential_b64"], 4096)
    if not credential or any(not 33 <= byte <= 126 for byte in credential):
        raise ValueError
    start, end = data["start_time"], data["end_time"]
    start_at, end_at = _seconds(start), _seconds(end)
    cursor = data["cursor"]
    if start >= end:
        raise ValueError
    if (data["provider"], data["profile"]) == ("deepgram", "DG_LISTEN_V1"):
        # quote() leaves dot segments unencoded. Never admit a dot path segment.
        parent_path = quote(parent, safe="")
        if parent_path in (".", ".."):
            parent_path = parent_path.replace(".", "%2E")
        query = urlencode({
            "start": start_at.isoformat().replace("+00:00", "Z"),
            "end": end_at.isoformat().replace("+00:00", "Z"),
            "limit": 100, "page": dg_page(cursor), "endpoint": "listen",
        })
        return (
            "api.deepgram.com", f"/v1/projects/{parent_path}/requests?{query}",
            {"Authorization": "Token " + credential.decode("ascii")},
        )
    if (data["provider"], data["profile"]) == ("openai", "OA_COMPLETIONS_1H_V1"):
        if start % 3600 or end % 3600 or end - start != 86400:
            raise ValueError
        query = [
            ("start_time", start), ("end_time", end), ("bucket_width", "1h"), ("limit", 24),
            *[("group_by", label) for label in ("project_id", "api_key_id", "model", "batch")],
        ]
        if cursor is not None:
            if not valid_cursor(cursor):
                raise ValueError
            query.append(("page", cursor))
        return (
            "api.openai.com", f"/v1/organization/usage/completions?{urlencode(query)}",
            {"Authorization": "Bearer " + credential.decode("ascii"), "OpenAI-Organization": parent},
        )
    raise ValueError


def _failure(code):
    return {"schema_version": 1, "kind": "failure", "code": code}


def _remaining(until, max_seconds):
    left = (until - time.monotonic_ns()) / 1_000_000_000
    if left <= 0:
        raise TimeoutError
    return min(left, max_seconds)


def http_read(host, path, headers, until):
    try:
        connection = http.client.HTTPSConnection(
            host, port=443, timeout=_remaining(until, 2), context=ssl.create_default_context(),
        )
        try:
            connection.connect()
        except TimeoutError:
            return _failure("CONNECT_TIMEOUT")
        try:
            headers = {**headers, "Accept": "application/json", "Accept-Encoding": "identity"}
            connection.sock.settimeout(_remaining(until, 5))
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            with response:
                if response.status != 200:
                    return {"schema_version": 1, "kind": "response", "status": response.status, "body_b64": ""}
                if response.getheader("Content-Encoding", "identity") != "identity":
                    return _failure("RESPONSE_PROTOCOL")
                body = bytearray()
                while len(body) <= MAX_BODY:
                    part = response.read1(min(16_384, MAX_BODY + 1 - len(body)))
                    if not part:
                        return {
                            "schema_version": 1, "kind": "response", "status": 200,
                            "body_b64": base64.b64encode(body).decode("ascii"),
                        }
                    body.extend(part)
                return _failure("RESPONSE_TOO_LARGE")
        finally:
            connection.close()
    except TimeoutError:
        return _failure("READ_TIMEOUT")
    except (OSError, http.client.HTTPException, ValueError):
        return _failure("TRANSPORT_FAILURE")


def _pairs(pairs):
    mapping = dict(pairs)
    if len(mapping) != len(pairs):
        raise ValueError
    return mapping


def _input():
    size, = struct.unpack("!I", sys.stdin.buffer.read(4))
    if not 0 < size <= MAX_INPUT:
        raise ValueError
    payload = sys.stdin.buffer.read(size)
    if len(payload) != size:
        raise ValueError
    return json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    local_end = time.monotonic_ns() + 9_000_000_000
    signal.setitimer(signal.ITIMER_REAL, 9)
    try:
        data = _input()
        host, path, headers = invocation(data)
        until = min(local_end, data["io_deadline_ns"])
        signal.setitimer(signal.ITIMER_REAL, _remaining(until, 9))
    except TimeoutError:
        result = _failure("ABSOLUTE_TIMEOUT")
    except (ValueError, TypeError, struct.error, OverflowError, RecursionError):
        result = _failure("INPUT_PROTOCOL")
    else:
        result = http_read(host, path, headers, until)
    sys.stdout.buffer.write(frame(result))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
