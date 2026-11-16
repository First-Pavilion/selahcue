"""Real isolated subprocesses and loopback HTTP only. Production URLs stay fixed."""
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from threading import Thread
from time import monotonic, monotonic_ns, sleep
from uuid import uuid4

import pytest

from selahcue_api.apps.providers.adapters import grants_child, grants_transport as transport
from selahcue_api.apps.providers.contracts import MintFailureCode as Code, SecretBytes
from selahcue_api.apps.providers.minting import MintDispatch, SttDispatchAuthorization
from selahcue_api.apps.providers.stt_audit import wire_time

pytestmark = pytest.mark.django_db
CHILD = Path(grants_child.__file__).resolve()


def dispatch(*, horizon=30, limit=4):
    now, mono = datetime.now(UTC), monotonic_ns()
    end = mono + int(limit * 1_000_000_000)
    authority = SttDispatchAuthorization(
        uuid4(), uuid4(), uuid4(), uuid4(), 1, 42,
        "synthetic-project", "synthetic-project", "synthetic-key", SecretBytes(b"synthetic-grant-parent"),
        now, mono, now + timedelta(seconds=horizon), mono + int(horizon * 1_000_000_000),
    )
    return MintDispatch(authority, now, mono, end, end - 500_000_000)


def _stub(tmp_path, monkeypatch, program):
    child = tmp_path / "task5_child_fixture.py"
    child.write_text(program)
    monkeypatch.setattr(transport, "_CHILD", child)


@pytest.fixture
def listened():
    with socket.socket() as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        endpoint.listen()
        endpoint.settimeout(4)
        yield endpoint


def network_fixture(tmp_path, monkeypatch, port, delay=0):
    _stub(tmp_path, monkeypatch, f"""
import http.client
import os
import runpy
import time

assert set(os.environ) <= {{"PATH", "LANG", "LC_ALL", "LC_CTYPE", "__CF_USER_TEXT_ENCODING"}}
class Loopback(http.client.HTTPConnection):
    def __init__(self, host, *, timeout, context):
        assert host == 'api.deepgram.com'
        assert timeout <= 2
        super().__init__('127.0.0.1', {port}, timeout=timeout)
    def connect(self):
        super().connect()
        time.sleep({delay!r})
    def request(self, method, url, *args, **kwargs):
        assert method == 'POST' and url == '/v1/auth/grant'
        super().request(method, url, *args, **kwargs)
http.client.HTTPSConnection = Loopback
runpy.run_path({str(CHILD)!r}, run_name='__main__')
""")


@pytest.mark.parametrize("mode", ["success", "trickle", "oversized", "truncated"])
def test_actual_child_can_read_only_a_bounded_loopback_reply(listened, tmp_path, monkeypatch, mode):
    network_fixture(tmp_path, monkeypatch, listened.getsockname()[1])
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("TASK5_TEST_PARENT_ONLY", "synthetic")
    seen = []

    def server():
        conn, _ = listened.accept()
        with conn:
            conn.settimeout(2)
            data = b""
            while b'{"ttl_seconds":30}' not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            seen.append(data)
            try:
                if mode == "success":
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}")
                elif mode == "oversized":
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 16385\r\n\r\n")
                elif mode == "truncated":
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n{}")
                else:
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 200\r\n\r\n")
                    for _ in range(50):
                        conn.sendall(b"x")
                        sleep(0.1)
            except (BrokenPipeError, ConnectionResetError):
                pass

    worker = Thread(target=server)
    worker.start()
    started = monotonic()
    result = transport.run_grant_transport(dispatch())
    elapsed = monotonic() - started
    worker.join(timeout=6)
    assert not worker.is_alive()
    assert elapsed <= 4
    assert seen and b"Authorization: Token synthetic-grant-parent" in seen[0]
    assert seen[0].startswith(b"POST /v1/auth/grant HTTP/1.1")
    if mode == "success":
        assert result.status == 200 and result.body == b"{}" and result.response_received_at.tzinfo is UTC
        assert 'body=' not in repr(result)
    else:
        assert isinstance(result, transport.TransportFailure) and result.before_http is False
        assert result.code == (Code.TRANSPORT_TIMEOUT if mode == "trickle" else Code.TRANSPORT_ERROR)
    print(f"isolated child {mode}: {elapsed:.3f}s, {type(result).__name__}")


def test_real_child_checks_send_horizon_after_a_delayed_connect(listened, tmp_path, monkeypatch):
    network_fixture(tmp_path, monkeypatch, listened.getsockname()[1], delay=0.9)
    received = []

    def server():
        conn, _ = listened.accept()
        with conn:
            conn.settimeout(4)
            received.append(conn.recv(8192))

    worker = Thread(target=server)
    worker.start()
    result = transport.run_grant_transport(dispatch(horizon=0.65))
    worker.join(timeout=4)
    assert not worker.is_alive()
    assert received == [b""]
    assert result == transport.TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)


@pytest.mark.parametrize("mutation", ["endpoint", "unknown", "duplicate"])
def test_production_child_rejects_invalid_prepare_without_go(mutation):
    now = datetime.now(UTC)
    fields = {
        "kind": "prepare", "credential_b64": "Zml4dHVyZQ==",
        "send_not_after_ns": monotonic_ns() + 2_000_000_000,
        "io_deadline_ns": monotonic_ns() + 3_000_000_000,
        "send_not_after_utc": wire_time(now + timedelta(seconds=2)),
    }
    if mutation != "duplicate":
        fields[mutation] = "http://127.0.0.1"
    data = grants_child.frame(fields)
    if mutation == "duplicate":
        import struct

        body = data[4:-1] + b',"kind":"prepare"}'
        data = struct.pack(">I", len(body)) + body
    process = subprocess.run([sys.executable, "-I", str(CHILD)], input=data, capture_output=True,
                             timeout=4, env={"PATH": "/usr/bin:/bin"})
    assert process.returncode == 0
    assert grants_child.parse_frame(process.stdout[4:]) == {
        "schema_version": 1, "kind": "failure", "phase": "before_http", "code": "INPUT_PROTOCOL",
    }


def test_production_child_has_independent_timer_while_parent_pauses_before_go():
    process = subprocess.Popen(
        [sys.executable, "-I", str(CHILD)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin"}, start_new_session=True,
    )
    started = monotonic()
    try:
        process.stdin.write(grants_child.frame({
            "kind": "prepare", "credential_b64": "Zml4dHVyZQ==",
            "send_not_after_ns": monotonic_ns() + 1_000_000_000,
            "io_deadline_ns": monotonic_ns() + 1_000_000_000,
            "send_not_after_utc": wire_time(datetime.now(UTC) + timedelta(seconds=1)),
        }))
        process.stdin.flush()
        assert transport._read_frame(process.stdout, 128, monotonic_ns() + 500_000_000) == {
            "schema_version": 1, "kind": "ready",
        }
        assert process.wait(timeout=3) == -signal.SIGALRM
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
        process.stdin.close()
        process.stdout.close()
    assert 0.8 <= monotonic() - started < 3


def test_expired_authority_never_spawns(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Expired dispatch spawned a child")

    monkeypatch.setattr(transport.subprocess, "Popen", forbidden)
    result = transport.run_grant_transport(dispatch(horizon=-0.001))
    assert result == transport.TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)


@pytest.mark.parametrize("mode", ["stall", "bad-frame", "exit"])
def test_unproven_post_go_child_failure_never_becomes_definite(tmp_path, monkeypatch, mode):
    operation = {
        "stall": "time.sleep(60)",
        "bad-frame": "os.write(1, struct.pack('>I', 25000)); time.sleep(60)",
        "exit": "sys.exit(77)",
    }[mode]
    _stub(tmp_path, monkeypatch, f"""
import os, struct, sys, time
size, = struct.unpack('>I', sys.stdin.buffer.read(4))
sys.stdin.buffer.read(size)
ready = b'{{"schema_version":1,"kind":"ready"}}'
os.write(1, struct.pack('>I', len(ready)) + ready)
size, = struct.unpack('>I', sys.stdin.buffer.read(4))
sys.stdin.buffer.read(size)
{operation}
""")
    original = subprocess.Popen
    children = []

    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(transport.subprocess, "Popen", spawn)
    started = monotonic()
    verdict = transport.run_grant_transport(dispatch())
    elapsed = monotonic() - started
    assert verdict.before_http is False
    assert verdict.code == (Code.TRANSPORT_TIMEOUT if mode == "stall" else Code.TRANSPORT_ERROR)
    assert len(children) == 1 and children[0].returncode is not None
    assert elapsed <= 4
    print(f"isolated child post-GO {mode}: {elapsed:.3f}s; reaped exit={children[0].returncode}")


def test_cancellation_kills_and_reaps_child(tmp_path, monkeypatch):
    _stub(tmp_path, monkeypatch, "import time\ntime.sleep(60)\n")
    original = subprocess.Popen
    children = []

    def spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child

    class SimulatedCancellation(BaseException):
        pass

    def cancel(*args):
        raise SimulatedCancellation

    monkeypatch.setattr(transport.subprocess, "Popen", spawn)
    monkeypatch.setattr(transport, "_read_frame", cancel)
    with pytest.raises(SimulatedCancellation):
        transport.run_grant_transport(dispatch())
    assert len(children) == 1 and children[0].returncode == -signal.SIGKILL


@pytest.mark.parametrize("phase", ["dns", "tls"])
def test_real_isolated_child_bounds_pre_http_dns_and_tls_stalls(listened, tmp_path, monkeypatch, phase):
    patch = (
        "socket.getaddrinfo = lambda *args, **kwargs: time.sleep(60)"
        if phase == "dns" else (
            "connect = socket.create_connection\n"
            f"socket.create_connection = lambda addr, *a, **kw: connect(('127.0.0.1', {listened.getsockname()[1]}), *a, **kw)"
        )
    )
    _stub(tmp_path, monkeypatch, f"""
import socket, time, runpy
{patch}
runpy.run_path({str(CHILD)!r}, run_name='__main__')
""")
    received = []
    worker = None
    if phase == "tls":
        def stall_tls():
            connection, _ = listened.accept()
            with connection:
                connection.settimeout(4)
                received.append(connection.recv(4096))
                received.append(connection.recv(4096))
        worker = Thread(target=stall_tls)
        worker.start()
    started = monotonic()
    result = transport.run_grant_transport(dispatch())
    elapsed = monotonic() - started
    if worker is not None:
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert received[0].startswith(b"\x16")  # TLS ClientHello, no HTTP.
        assert received[-1] == b""
        assert result == transport.TransportFailure(Code.REQUEST_REJECTED_LOCALLY, True)
    else:
        assert result == transport.TransportFailure(Code.TRANSPORT_TIMEOUT, False)
    assert 1.5 <= elapsed <= 4
    print(f"isolated child {phase} stall: {elapsed:.3f}s")


def test_unreaped_process_terminates_only_the_worker_harness():
    launcher = """
from subprocess import TimeoutExpired
from time import monotonic_ns
from selahcue_api.apps.providers.adapters.grants_transport import _cleanup
class Pipe:
    def close(self):
        pass
class Child:
    stdin = stdout = Pipe()
    def wait(self, timeout):
        raise TimeoutExpired('synthetic process', timeout)
_cleanup(Child(), monotonic_ns() + 10_000_000, kill=False)
"""
    result = subprocess.run(
        [sys.executable, "-c", launcher], env={"PATH": "/usr/bin:/bin"},
        timeout=3, capture_output=True,
    )
    assert result.returncode == 78
    assert result.stdout == result.stderr == b""


def test_suspended_parent_cannot_refresh_child_send_horizon():
    import selectors

    script = f"""
from datetime import UTC, datetime, timedelta
import os, signal, subprocess, sys
from time import monotonic_ns
from selahcue_api.apps.providers.adapters.grants_child import frame
from selahcue_api.apps.providers.adapters.grants_transport import _read_frame
child = subprocess.Popen([sys.executable, '-I', {str(CHILD)!r}], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
now = monotonic_ns()
child.stdin.write(frame({{
    'kind':'prepare', 'credential_b64':'Zml4dHVyZQ==',
    'send_not_after_ns':now+1_000_000_000, 'io_deadline_ns':now+1_000_000_000,
    'send_not_after_utc':(datetime.now(UTC)+timedelta(seconds=1)).isoformat(timespec='microseconds').replace('+00:00','Z'),
}}))
child.stdin.flush()
assert _read_frame(child.stdout, 128, now+500_000_000)['kind']=='ready'
print("ready-to-suspend", flush=True)
os.kill(os.getpid(), signal.SIGSTOP)
assert child.wait(timeout=1) == -signal.SIGALRM
child.stdin.close()
child.stdout.close()
print("reaped-without-go", flush=True)
"""
    controller = subprocess.Popen(
        [sys.executable, "-c", script], env={"PATH": "/usr/bin:/bin"},
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(controller.stdout, selectors.EVENT_READ)
            assert selector.select(3)
        assert controller.stdout.readline() == b"ready-to-suspend\n"
        sleep(1.2)
        os.kill(controller.pid, signal.SIGCONT)
        reply, _ = controller.communicate(timeout=4)
        assert reply == b"reaped-without-go\n" and controller.returncode == 0
    finally:
        if controller.poll() is None:
            os.killpg(controller.pid, signal.SIGKILL)
            controller.wait(timeout=2)
        controller.stdout.close()
