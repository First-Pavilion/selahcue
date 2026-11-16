"""One framed HTTPS exchange, run with Python -I and the standard library only."""
import base64
import binascii
import http.client
import json
import re
import signal
import socket
import ssl
import struct
import sys
from time import monotonic
from urllib.parse import quote, unquote, urlencode

INPUT_MAX = 16_384
WRITE_MAX = 1024 * 1024
READ_MAX = 4 * WRITE_MAX
ID = re.compile(r"[!-~]{1,256}")
REQUEST_FIELDS = {
    "schema_version", "provider", "parent_scope_id", "method", "path", "query",
    "body", "credential_b64", "absolute_timeout_ms",
}
MARKER = r"scp1-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}-"


def identifier(value):
    return type(value) is str and ID.fullmatch(value) is not None


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def invalid_number(_):
    raise ValueError


def loads(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_number)


def _segment(value):
    decoded = unquote(value, errors="strict")
    if not identifier(decoded) or quote(decoded, safe="") != value or value in (".", ".."):
        raise ValueError
    return decoded


def _name(body, field, suffix, extras=None):
    if type(body) is not dict:
        return False
    label = body.get(field)
    return (
        type(label) is str and re.fullmatch(MARKER + suffix, label) is not None
        and body == {field: label, **(extras or {})}
    )


def _deepgram(parent, method, segments, query, body):
    if len(segments) < 5 or segments[:3] != ["", "v1", "projects"] or segments[4] != "keys":
        return False
    if _segment(segments[3]) != parent or query:
        return False
    if len(segments) == 5:
        return (method == "GET" and body is None) or (
            method == "POST" and _name(body, "comment", "dgkey", {"scopes": ["member"]})
        )
    return len(segments) == 6 and method == "DELETE" and body is None and identifier(_segment(segments[5]))


def _read_query(query, extras=None):
    expected = {"limit": 100, **(extras or {})}
    if "after" in query:
        if not identifier(query["after"]):
            return False
        expected["after"] = query["after"]
    return type(query.get("limit")) is int and query == expected


def _openai(method, segments, query, body):
    if segments[:4] != ["", "v1", "organization", "projects"]:
        return False
    if len(segments) == 4:
        return ((method == "GET" and body is None and _read_query(query, {"include_archived": "true"}))
                or (method == "POST" and not query and _name(body, "name", "oaproj")))
    if len(segments) not in (6, 7) or not identifier(_segment(segments[4])):
        return False
    collection = segments[5]
    if len(segments) == 7:
        return (
            collection in ("service_accounts", "api_keys") and method == "DELETE"
            and body is None and not query and identifier(_segment(segments[6]))
        )
    if collection == "service_accounts":
        return ((method == "GET" and body is None and _read_query(query))
                or (method == "POST" and not query and _name(body, "name", "oasvc")))
    if collection == "api_keys":
        return method == "GET" and body is None and _read_query(query, {"owner_project_access": "any"})
    return collection == "archive" and method == "POST" and body is None and not query


def request_fields(value):
    if type(value) is not dict or value.keys() != REQUEST_FIELDS:
        raise ValueError
    provider, parent, method, path, query, body, limit = (
        value[field] for field in ("provider", "parent_scope_id", "method", "path", "query", "body", "absolute_timeout_ms")
    )
    if (
        type(value["schema_version"]) is not int or value["schema_version"] != 1
        or not identifier(parent) or method not in ("GET", "POST", "DELETE")
        or type(path) is not str or type(query) is not dict
        or type(limit) is not int or not 0 < limit <= 9000
        or type(value["credential_b64"]) is not str
    ):
        raise ValueError
    credential = base64.b64decode(value["credential_b64"], validate=True)
    if not re.fullmatch(rb"[!-~]{1,4096}", credential) or base64.b64encode(credential).decode() != value["credential_b64"]:
        raise ValueError
    segments = path.split("/")
    if provider == "deepgram" and _deepgram(parent, method, segments, query, body):
        host = "api.deepgram.com"
        headers = {"Authorization": "Token " + credential.decode("ascii")}
    elif provider == "openai" and _openai(method, segments, query, body):
        host = "api.openai.com"
        headers = {"Authorization": "Bearer " + credential.decode("ascii"), "OpenAI-Organization": parent}
    else:
        raise ValueError
    raw = None if body is None else json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
    if raw is not None:
        headers["Content-Type"] = "application/json"
    return host, method, path + ("?" + urlencode(query) if query else ""), headers, raw, limit


def failure(code, *, before_http=False):
    return {"schema_version": 1, "kind": "failure", "code": code,
            "phase": "before_http" if before_http else "possible_dispatch"}


def exchange(host, method, path, headers, body, timeout, started):
    end = started + timeout / 1000
    maximum = READ_MAX if method == "GET" else WRITE_MAX
    con = None
    try:
        connect_timeout = min(2, end - monotonic())
        if connect_timeout <= 0:
            return failure("ABSOLUTE_TIMEOUT", before_http=True)
        con = http.client.HTTPSConnection(host, 443, timeout=connect_timeout, context=ssl.create_default_context())
        try:
            con.connect()
        except socket.timeout:
            return failure("CONNECT_TIMEOUT")
        read_timeout = min(5, end - monotonic())
        if read_timeout <= 0:
            return failure("ABSOLUTE_TIMEOUT")
        con.sock.settimeout(read_timeout)
        con.request(method, path, body=body, headers=headers)
        with con.getresponse() as response:
            advertised = response.getheader("Content-Length")
            if advertised is not None and (not advertised.isascii() or not advertised.isdigit()):
                return failure("RESPONSE_PROTOCOL")
            if advertised is not None and (len(advertised) > 10 or int(advertised) > maximum):
                return failure("RESPONSE_TOO_LARGE")
            pieces = bytearray()
            while len(pieces) <= maximum:
                if monotonic() >= end:
                    return failure("ABSOLUTE_TIMEOUT")
                data = response.read(min(64 * 1024, maximum + 1 - len(pieces)))
                if not data:
                    break
                pieces.extend(data)
            if len(pieces) > maximum:
                return failure("RESPONSE_TOO_LARGE")
            if advertised is not None and len(pieces) != int(advertised):
                return failure("RESPONSE_PROTOCOL")
            request_id = response.getheader("x-request-id")
            return {
                "schema_version": 1, "kind": "response", "status": response.status,
                "request_id": request_id if identifier(request_id) else None,
                "body_b64": base64.b64encode(pieces).decode("ascii"),
            }
    except socket.timeout:
        return failure("READ_TIMEOUT")
    except http.client.HTTPException:
        return failure("RESPONSE_PROTOCOL")
    except (OSError, ValueError):
        return failure("TRANSPORT_FAILURE")
    finally:
        if con is not None:
            con.close()


def run():
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, 9)
    started = monotonic()
    stream = sys.stdin.buffer
    header = stream.read(4)
    if len(header) != 4 or not 0 < (size := struct.unpack("!I", header)[0]) <= INPUT_MAX:
        return failure("INPUT_PROTOCOL", before_http=True)
    raw = stream.read(size)
    if len(raw) != size:
        return failure("INPUT_PROTOCOL", before_http=True)
    try:
        request = request_fields(loads(raw))
    except (ValueError, TypeError, OverflowError, binascii.Error):
        return failure("VALIDATION", before_http=True)
    return exchange(*request, started)


if __name__ == "__main__":
    payload = json.dumps(run(), ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("!I", len(payload)))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()
