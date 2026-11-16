"""Inspect the actual sync Gunicorn WSGI framing on a private loopback server."""
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
from time import monotonic, sleep

import pytest

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[1]
BODY = json.dumps({
    "idempotency_key": "12345678-1234-1234-1234-000000000001", "action": "start", "socket": "new",
    "consent_version": "stt-direct-audio-v1", "policy_version": "stt-direct-v1",
}).encode()


@pytest.fixture(scope="module")
def gunicorn(tmp_path_factory):
    folder = tmp_path_factory.mktemp("stt-gunicorn")
    audit = folder / "trace"
    audit.touch()
    wrapper = folder / "task5_ingress.py"
    wrapper.write_text(
        "from selahcue_api.wsgi import application\n"
        "from selahcue_api.platform import cloud_views\n"
        "from selahcue_api.graphql.errors import SafeAPIError, ErrorCode\n"
        "from pathlib import Path\n"
        f"trace = Path({str(audit)!r})\n"
        "parse = cloud_views._session_request\n"
        "def tracing_parse(request):\n"
        "    with trace.open('a') as output: output.write('parse\\n')\n"
        "    return parse(request)\n"
        "def denied(request):\n"
        "    with trace.open('a') as output: output.write('auth\\n')\n"
        "    raise SafeAPIError(ErrorCode.UNAUTHENTICATED)\n"
        "cloud_views._session_request = tracing_parse\n"
        "cloud_views._authenticate = denied\n"
    )
    with socket.socket() as listen:
        listen.bind(("127.0.0.1", 0))
        listen.listen()
        port = listen.getsockname()[1]
        with (folder / "server.log").open("w+") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "gunicorn", "-c", str(ROOT / "gunicorn.conf.py"),
                 "--bind", f"fd://{listen.fileno()}", "--workers", "1", "--pythonpath", str(folder),
                 "task5_ingress:application"],
                cwd=ROOT, start_new_session=True, stdout=log, stderr=log, pass_fds=(listen.fileno(),),
                env={"PATH": "/usr/bin:/bin", "SQL_DATABASE": str(folder / "synthetic.sqlite3")},
            )
            try:
                started = monotonic()
                while True:
                    log.seek(0)
                    contents = log.read()
                    if "Booting worker" in contents:
                        break
                    assert process.poll() is None, contents
                    assert monotonic() - started < 10, contents
                    sleep(0.025)
                yield port, audit
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                except ProcessLookupError:
                    process.wait(timeout=5)


def request(port, headers, body, *, eof=False, timeout=4):
    result = bytearray()
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as client:
        client.sendall(
            b"POST /v1/stt/session HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n"
            b"Content-Type: application/json\r\n" + headers + b"\r\n" + body
        )
        if eof:
            client.shutdown(socket.SHUT_WR)
        try:
            while len(result) < 128 * 1024:
                part = client.recv(4096)
                if not part:
                    break
                result.extend(part)
        except ConnectionResetError:
            pass
    return bytes(result)


@pytest.mark.parametrize(("headers", "body", "eof", "status", "visited"), [
    (b"Content-Length: %d\r\n" % len(BODY), BODY, False, 401, ["parse", "auth"]),
    (b"", BODY, False, 400, ["parse"]),
    (b"Content-Length: garbage\r\n", BODY, False, 400, []),
    (b"Content-Length: -1\r\n", BODY, False, 400, []),
    (b"Content-Length: 1,1\r\n", BODY, False, 400, []),
    (b"Content-Length: 1\r\nContent-Length: 2\r\n", BODY, False, 400, []),
    (b"Transfer-Encoding: chunked\r\n", b"1\r\nx\r\n0\r\n\r\n", False, 400, ["parse"]),
    (b"Transfer-Encoding: chunked\r\nContent-Length: 1\r\n", BODY, False, 400, []),
    (b"Content-Length: 8193\r\n", b"", False, 400, ["parse"]),
    (b"Content-Length: 0\r\n", b"", False, 400, ["parse"]),
    (b"Content-Length: 1\r\n", BODY, False, 400, ["parse"]),
    (b"Content-Length: %d\r\n" % (len(BODY) + 3), BODY, True, 400, ["parse"]),
    (b"Content-Length: %d\r\n" % len(BODY), BODY + b"trailing-wire-bytes", False, 401, ["parse", "auth"]),
])
def test_gunicorn_framing(gunicorn, headers, body, eof, status, visited):
    port, trace = gunicorn
    before = len(trace.read_text().splitlines())
    response = request(port, headers, body, eof=eof)
    observed = re.match(rb"HTTP/1\.[01] ([0-9]{3})", response)
    calls = trace.read_text().splitlines()[before:]
    assert calls == visited, response
    assert observed is not None and int(observed[1]) == status, response
    if visited:
        head, _, payload = response.partition(b"\r\n\r\n")
        assert b"cache-control: no-store" in head.lower()
        assert json.loads(payload)["error"]["code"] == ("UNAUTHENTICATED" if status == 401 else "VALIDATION_FAILED")
    else:
        assert b'"surface"' not in response
    print(f"Gunicorn framed request: {status}, app={bool(visited)} auth={'auth' in calls} header={headers!r}")


def test_incomplete_no_eof_reaches_worker_timeout(gunicorn):
    port, trace = gunicorn
    before = len(trace.read_text().splitlines())
    started = monotonic()
    response = request(port, b"Content-Length: %d\r\n" % (len(BODY) + 4), BODY, timeout=39)
    elapsed = monotonic() - started
    calls = trace.read_text().splitlines()[before:]
    assert calls == ["parse"]
    assert 27 <= elapsed < 39
    assert b'"surface"' not in response
    print(f"Gunicorn worker timeout: {elapsed:.3f}s, reply={response[:64]!r}; parse entered, auth untouched")
