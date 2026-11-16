import base64
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db

CHILD = Path(__file__).resolve().parents[1] / "selahcue_api/apps/providers/adapters/transport_child.py"


def frame(value):
    body = json.dumps(value).encode()
    return struct.pack("!I", len(body)) + body


def plain_request(parent):
    return {
        "schema_version": 1, "provider": "deepgram", "parent_scope_id": parent, "method": "GET",
        "path": "/v1/projects/synthetic-project/keys", "query": {}, "body": None,
        "credential_b64": base64.b64encode(b"synthetic-credential").decode(), "absolute_timeout_ms": 9000,
    }


@pytest.mark.parametrize("parent", [None, "another-parent", " spaces", ""])
def test_child_refuses_unbound_parent_before_http(parent):
    result = subprocess.run([sys.executable, "-I", str(CHILD)], input=frame(plain_request(parent)),
                            capture_output=True, timeout=4)
    assert result.returncode == 0
    assert json.loads(result.stdout[4:]) == {
        "schema_version": 1, "kind": "failure", "phase": "before_http", "code": "VALIDATION",
    }
    assert len(result.stdout) - 4 == struct.unpack("!I", result.stdout[:4])[0]
    assert b"synthetic-credential" not in result.stderr


def _loopback_child(tmp_path, prelude):
    harness = tmp_path / "fixed_loopback_child.py"
    # The harness runs the standalone child unchanged except for its HTTP
    # connection factory, which always targets a test-owned loopback listener.
    harness.write_text(
        "import runpy, sys, json, struct\n"
        f"child = runpy.run_path({str(CHILD)!r})\n"
        "run = child['run']\n"
        "import http.client, os, signal, socket, time\n"
        + prelude + "\n"
        "result = json.dumps(run()).encode()\n"
        "sys.stdout.buffer.write(struct.pack('!I', len(result)) + result)\n"
    )
    return harness


@pytest.mark.django_db(transaction=True)
def test_loopback_child_uses_exact_openai_parent_header(tmp_path, monkeypatch):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    from selahcue_api.apps.providers.adapters import transport
    from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningCredential, SecretBytes

    headers = []

    class Capture(BaseHTTPRequestHandler):
        def do_GET(self):
            headers.append((self.path, self.headers.get("OpenAI-Organization"), self.headers.get("Authorization")))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), Capture) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            harness = _loopback_child(tmp_path, (
                "def loopback(host, port, *, timeout, context):\n"
                "    assert host == 'api.openai.com' and port == 443\n"
                f"    return http.client.HTTPConnection('127.0.0.1', {server.server_port}, timeout=timeout)\n"
                "http.client.HTTPSConnection = loopback\n"
                "assert 'TASK4_SANDBOX_SECRET' not in os.environ"
            ))
            monkeypatch.setenv("TASK4_SANDBOX_SECRET", "must-not-reach-child")
            monkeypatch.setattr(transport, "_CHILD", harness)
            for parent in ("synthetic-org-alpha", "synthetic-org-beta"):
                credential = ProvisioningCredential(ProviderScope("openai", parent), SecretBytes(b"bounded-test-key"))
                result = transport._send(transport._Operation(
                    "GET", "/v1/organization/projects", {"limit": 100, "include_archived": "true"},
                ), credential)
                assert isinstance(result, transport._Response) and result.status == 200
        finally:
            server.shutdown()
            thread.join(timeout=2)
    assert headers == [
        ("/v1/organization/projects?limit=100&include_archived=true", parent, "Bearer bounded-test-key")
        for parent in ("synthetic-org-alpha", "synthetic-org-beta")
    ]


@pytest.mark.django_db(transaction=True)
def test_stalled_dns_child_is_killed_and_reaped_under_absolute_budget(tmp_path, monkeypatch):
    import os
    from time import monotonic

    from selahcue_api.apps.providers.adapters import transport
    from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningCredential, SecretBytes

    pidfile = tmp_path / "pid"
    harness = _loopback_child(tmp_path, (
        "def stall_dns(*args, **kwargs):\n"
        f"    open({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
        "    time.sleep(60)\n"
        "socket.getaddrinfo = stall_dns"
    ))
    monkeypatch.setattr(transport, "_CHILD", harness)
    scope = ProviderScope("deepgram", "synthetic-project")
    started = monotonic()
    result = transport._send(transport._Operation("GET", "/v1/projects/synthetic-project/keys"),
                             ProvisioningCredential(scope, SecretBytes(b"synthetic-key")))
    elapsed = monotonic() - started
    assert isinstance(result, transport._Failure) and result.phase == "possible_dispatch"
    assert 8.5 <= elapsed < 10.0
    assert pidfile.exists()
    with pytest.raises(ChildProcessError):
        os.waitpid(int(pidfile.read_text()), os.WNOHANG)


@pytest.mark.django_db(transaction=True)
def test_bad_reply_frame_is_killed_without_waiting_for_eof(tmp_path, monkeypatch):
    import os
    from time import monotonic

    from selahcue_api.apps.providers.adapters import transport
    from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningCredential, SecretBytes

    harness = tmp_path / "bad.py"
    pidfile = tmp_path / "bad_pid"
    harness.write_text(
        f"import os,struct,sys,time\nopen({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
        "sys.stdin.buffer.read()\n"
        "sys.stdout.buffer.write(struct.pack('!I', 99999999))\nsys.stdout.buffer.flush()\ntime.sleep(60)\n"
    )
    monkeypatch.setattr(transport, "_CHILD", harness)
    scope = ProviderScope("deepgram", "synthetic-project")
    started = monotonic()
    result = transport._send(transport._Operation("GET", "/v1/projects/synthetic-project/keys"),
                             ProvisioningCredential(scope, SecretBytes(b"synthetic-key")))
    assert result == transport._Failure("possible_dispatch", "RESPONSE_TOO_LARGE")
    assert monotonic() - started < 2
    with pytest.raises(ChildProcessError):
        os.waitpid(int(pidfile.read_text()), os.WNOHANG)


def test_one_time_secret_requires_explicit_null_expiry_and_never_repr(monkeypatch):
    from uuid import uuid4
    from selahcue_api.apps.providers.adapters import deepgram_admin, transport
    from selahcue_api.apps.providers.adapters.contracts import AdminRequest, Created, MutationUnknown
    from selahcue_api.apps.providers.contracts import (
        AdminOperation, ProviderScope, ProvisioningCredential, ProvisioningErrorCode, SecretBytes,
    )

    scope = ProviderScope("deepgram", "test-project")
    request = AdminRequest(AdminOperation.DG_CREATE_KEY, scope, uuid4(), uuid4(), "synthetic-marker", "test-project", None, None)
    credential = ProvisioningCredential(scope, SecretBytes(b"test-admin-secret"))

    without = {"api_key_id": "key-reference", "key": "test-one-time-secret"}
    for fields, control in [(without, MutationUnknown), ({**without, "expiration_date": None}, Created)]:
        monkeypatch.setattr(transport, "_send", lambda *_: transport._Response(200, "test-request", json.dumps(fields).encode()))
        result = deepgram_admin.mutate(request, credential)
        assert isinstance(result, control)
        assert "test-one-time-secret" not in repr(result)
        if isinstance(result, MutationUnknown):
            assert result.code == ProvisioningErrorCode.RESPONSE_INVALID
            assert result.known_identity.api_key_id == "key-reference"


@pytest.mark.django_db(transaction=True)
def test_loopback_slow_body_cannot_extend_absolute_deadline(tmp_path, monkeypatch):
    import os
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Event, Thread
    from time import monotonic

    from selahcue_api.apps.providers.adapters import transport
    from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningCredential, SecretBytes

    served = Event()
    stopped = Event()
    pidfile = tmp_path / "slow_pid"

    class SlowBody(BaseHTTPRequestHandler):
        def do_GET(self):
            served.set()
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            try:
                while not stopped.wait(0.15):
                    self.wfile.write(b"x")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), SlowBody) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            harness = _loopback_child(tmp_path, (
                "def loopback(host, port, *, timeout, context):\n"
                "    assert host == 'api.deepgram.com' and port == 443\n"
                f"    open({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
                f"    return http.client.HTTPConnection('127.0.0.1', {server.server_port}, timeout=timeout)\n"
                "http.client.HTTPSConnection = loopback"
            ))
            monkeypatch.setattr(transport, "_CHILD", harness)
            scope = ProviderScope("deepgram", "synthetic-project")
            started = monotonic()
            result = transport._send(transport._Operation("GET", "/v1/projects/synthetic-project/keys"),
                                     ProvisioningCredential(scope, SecretBytes(b"synthetic-key")))
            elapsed = monotonic() - started
            assert served.is_set()
            assert 8.5 <= elapsed < 10
            assert isinstance(result, transport._Failure) and result.phase == "possible_dispatch"
            with pytest.raises(ChildProcessError):
                os.waitpid(int(pidfile.read_text()), os.WNOHANG)
        finally:
            stopped.set()
            server.shutdown()
            thread.join(timeout=2)


@pytest.mark.parametrize("operation,body,confirmed", [
    ("OA_DELETE_SERVICE_ACCOUNT", {"object": "organization.project.service_account.deleted", "id": "account", "deleted": True}, True),
    ("OA_DELETE_SERVICE_ACCOUNT", {"object": "other", "id": "account", "deleted": True}, False),
    ("OA_ARCHIVE_PROJECT", {"object": "organization.project", "id": "project", "status": "archived", "archived_at": 12}, True),
    ("OA_ARCHIVE_PROJECT", {"object": "organization.project", "id": "project", "status": "archived", "archived_at": True}, False),
])
def test_openai_cleanup_accepts_only_exact_receipt(operation, body, confirmed, monkeypatch):
    from uuid import uuid4
    from selahcue_api.apps.providers.adapters import openai_admin, transport
    from selahcue_api.apps.providers.adapters.contracts import AdminRequest, CleanupConfirmed
    from selahcue_api.apps.providers.contracts import AdminOperation, ProviderScope, ProvisioningCredential, SecretBytes

    scope = ProviderScope("openai", "synthetic-org")
    request = AdminRequest(AdminOperation(operation), scope, uuid4(), uuid4(), "fixture", "project", "account", None)
    credential = ProvisioningCredential(scope, SecretBytes(b"synthetic-admin"))
    monkeypatch.setattr(transport, "_send", lambda *_: transport._Response(200, "test-request", json.dumps(body).encode()))
    assert isinstance(openai_admin.mutate(request, credential), CleanupConfirmed) is confirmed
