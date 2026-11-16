"""Inert child protocol and strict provider projection boundary cases."""
import os
import signal
import subprocess
import sys
import time

import pytest

from provider_helpers import DEEPGRAM
from selahcue_api.apps.providers.adapters import usage_transport
from selahcue_api.apps.providers.adapters.usage_child import frame
from selahcue_api.apps.usage.observation_contracts import UsageReadFailed
from test_provider_observations import COVERAGE, dg_data, parse_dg, request


@pytest.mark.parametrize("reply", [
    b"\0\0\0\0",
    b"\0\x20\0\0",
    b"\0\0\0\x06broken",
    frame({"schema_version": 1, "kind": "response", "status": 200, "body_b64": "%%%"}),
    frame({"schema_version": 1, "kind": "response", "status": 302, "body_b64": ""}),
    frame({"schema_version": 1, "kind": "response", "status": 200, "body_b64": "e30="}) + b"tail",
])
def test_inert_child_framing_and_base64_fail_closed(tmp_path, reply):
    stub = tmp_path / "reply.py"
    stub.write_text(
        "import sys\n"
        "sys.stdin.buffer.read(6)\n"
        f"sys.stdout.buffer.write({reply!r})\n"
        "sys.stdout.buffer.flush()\n"
    )
    with pytest.raises(UsageReadFailed, match="TRANSPORT_ERROR"):
        usage_transport._run({}, started=time.monotonic_ns(), child=stub)


def test_body_rejects_one_byte_past_the_retained_limit():
    with pytest.raises(UsageReadFailed, match="RESPONSE_TOO_LARGE"):
        usage_transport.metadata_json(b" " * 1_048_577)


@pytest.mark.parametrize("mutate", [
    lambda row: row.update(request_id="with whitespace"),
    lambda row: row.update(request_id="a" * 257),
    lambda row: row.update(response={"completed": "2026-11-15T11:59:00.0000001Z"}),
    lambda row: row.update(response={"completed": "2026-11-15T11:59:00"}),
    lambda row: row.update(response={"completed": False}),
])
def test_deepgram_rejects_incompatible_identity_and_completion(mutate):
    item = request()
    mutate(item)
    with pytest.raises(UsageReadFailed, match="INVALID_RESPONSE"):
        parse_dg(dg_data([item]))


@pytest.mark.skipif(os.name != "posix", reason="The production usage child requires POSIX signals")
def test_real_child_absolute_timer_stops_inert_stalled_http_without_parent_assistance(tmp_path):
    stub = tmp_path / "stall.py"
    entered = tmp_path / "entered"
    stub.write_text(
        "import pathlib, runpy, time\n"
        f"entry = runpy.run_path({str(usage_transport._CHILD)!r})['main']\n"
        "def stall(*args):\n"
        f"    pathlib.Path({str(entered)!r}).touch()\n"
        "    time.sleep(30)\n"
        "entry.__globals__['http_read'] = stall\n"
        "entry()\n"
    )
    start = time.monotonic_ns()
    message = {
        "schema_version": 1, "provider": "deepgram", "parent_scope_id": DEEPGRAM.parent_scope_id,
        "profile": "DG_LISTEN_V1", "start_time": int(COVERAGE.start.timestamp()),
        "end_time": int(COVERAGE.end.timestamp()), "cursor": None, "credential_b64": "c3ludGhldGlj",
        "io_deadline_ns": start + 500_000_000,
    }
    with subprocess.Popen(
        [sys.executable, "-I", str(stub)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, close_fds=True, env={"PATH": "/usr/bin:/bin"},
    ) as child:
        try:
            stdout, _ = child.communicate(frame(message), timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate(timeout=2)
            raise
    assert entered.exists()
    assert stdout == b""
    assert child.returncode == -signal.SIGALRM
    assert time.monotonic_ns() - start < 2_000_000_000


def _child_message(deadline_ns, **changes):
    return {
        "schema_version": 1, "provider": "deepgram", "parent_scope_id": DEEPGRAM.parent_scope_id,
        "profile": "DG_LISTEN_V1", "start_time": int(COVERAGE.start.timestamp()),
        "end_time": int(COVERAGE.end.timestamp()), "cursor": None, "credential_b64": "c3ludGhldGlj",
        "io_deadline_ns": deadline_ns, **changes,
    }


@pytest.mark.parametrize("change", [
    {"credential_b64": "%%%"}, {"credential_b64": "YQpi"}, {"provider": "openai"},
    {"url": "https://not-allowed.invalid"}, {"cursor": "not-an-index"},
])
def test_production_child_refuses_malformed_input_before_transport(change):
    import json

    payload = _child_message(time.monotonic_ns()+2_000_000_000, **change)
    child = subprocess.run(
        [sys.executable, "-I", str(usage_transport._CHILD)], input=frame(payload), capture_output=True,
        timeout=3, env={"PATH": "/usr/bin:/bin"}, check=True,
    )
    assert int.from_bytes(child.stdout[:4]) == len(child.stdout)-4
    assert json.loads(child.stdout[4:]) == {"schema_version": 1, "kind": "failure", "code": "INPUT_PROTOCOL"}


def test_production_child_refuses_input_frame_over_absolute_length():
    import json

    child = subprocess.run(
        [sys.executable, "-I", str(usage_transport._CHILD)], input=(32_769).to_bytes(4), capture_output=True,
        timeout=3, env={"PATH": "/usr/bin:/bin"}, check=True,
    )
    assert json.loads(child.stdout[4:])["code"] == "INPUT_PROTOCOL"


def test_production_child_wall_timer_interrupts_a_stalled_resolver_without_network(tmp_path):
    stub = tmp_path / "controlled_resolver.py"
    entered = tmp_path / "resolver-entered"
    stub.write_text(
        "import pathlib, runpy, socket, time\n"
        "def resolver(*args, **kwargs):\n"
        f"    pathlib.Path({str(entered)!r}).touch()\n"
        "    time.sleep(30)\n"
        "socket.getaddrinfo = resolver\n"
        f"runpy.run_path({str(usage_transport._CHILD)!r}, run_name='__main__')\n"
    )
    started = time.monotonic_ns() - 7_800_000_000
    with pytest.raises(UsageReadFailed, match="TRANSPORT_TIMEOUT"):
        usage_transport._run(_child_message(started + 9_000_000_000), started=started, child=stub)
    assert entered.exists()


@pytest.mark.parametrize("disruption", (signal.SIGSTOP, signal.SIGKILL))
def test_isolated_usage_child_cannot_survive_suspended_or_dead_parent(tmp_path, disruption):
    child = tmp_path / "held.py"
    ready = tmp_path / "ready"
    child.write_text(
        "import os,pathlib,runpy,time\n"
        f"entry=runpy.run_path({str(usage_transport._CHILD)!r})['main']\n"
        "def held(*args):\n"
        f"    pathlib.Path({str(ready)!r}).write_text(str(os.getpid()))\n"
        "    time.sleep(30)\n"
        "entry.__globals__['http_read']=held\n"
        "entry()\n"
    )
    parent_code = """
import os,subprocess,sys
lifetime=int(sys.argv[2])
with subprocess.Popen([sys.executable, '-I', sys.argv[1]], pass_fds=(lifetime,),
                      stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                      start_new_session=True, env={'PATH':'/usr/bin:/bin'}) as child:
    os.close(lifetime)
    child.communicate(sys.stdin.buffer.read(), timeout=6)
"""
    import select

    reader, lifetime = os.pipe()
    try:
        with subprocess.Popen(
            [sys.executable, "-I", "-c", parent_code, str(child), str(lifetime)],
            stdin=subprocess.PIPE, pass_fds=(lifetime,),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin"},
        ) as process:
            os.close(lifetime)
            lifetime = -1
            start = time.monotonic()
            try:
                process.stdin.write(frame(_child_message(time.monotonic_ns() + 1_500_000_000)))
                process.stdin.close()
                expiry = time.monotonic() + 1
                while not ready.exists() and time.monotonic() < expiry:
                    time.sleep(0.02)
                assert ready.exists()
                pid = int(ready.read_text())
                os.kill(process.pid, disruption)
                readable, _, _ = select.select([reader], [], [], 2.5)
                if not readable:
                    os.kill(pid, signal.SIGKILL)
                    pytest.fail("Usage child retained the lifetime pipe after its absolute deadline")
                assert os.read(reader, 1) == b""
                assert time.monotonic() - start < 3.5
            finally:
                if process.poll() is None and disruption == signal.SIGSTOP:
                    os.kill(process.pid, signal.SIGCONT)
                if process.poll() is None:
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
    finally:
        os.close(reader)
        if lifetime != -1:
            os.close(lifetime)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ("tls-handshake", "http-trickle"))
def test_actual_loopback_usage_network_stalls_respect_absolute_deadline(tmp_path, mode):
    import socket
    from threading import Event, Thread
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("Run inert socket checks in hosted CI while the local service hold applies")
    stop = Event()
    accepted = Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(3)
        port = listener.getsockname()[1]

        def server():
            sock, _ = listener.accept()
            with sock:
                accepted.set()
                if mode == "tls-handshake":
                    stop.wait(3)
                    return
                sock.settimeout(1)
                sock.recv(4096)
                try:
                    sock.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 20000\r\n\r\n")
                    while not stop.wait(0.03):
                        sock.sendall(b" ")
                except OSError:
                    pass

        fixture = Thread(target=server, daemon=True)
        fixture.start()
        stub = tmp_path / "transport.py"
        if mode == "tls-handshake":
            # The stdlib constructor resolves HTTPSConnection in its explicit super() call.
            redirect = (
                "original=http.client.HTTPSConnection.__init__\n"
                "def loopback(self, host, *, port, timeout, context):\n"
                "    assert (host,port)==('api.deepgram.com',443)\n"
                f"    original(self, '127.0.0.1', port={port}, timeout=timeout, context=context)\n"
                "http.client.HTTPSConnection.__init__=loopback\n"
            )
        else:
            redirect = (
                "original=http.client.HTTPConnection\n"
                "def loopback(host, *, port, timeout, context):\n"
                "    assert (host,port)==('api.deepgram.com',443)\n"
                f"    return original('127.0.0.1', port={port}, timeout=timeout)\n"
                "http.client.HTTPSConnection=loopback\n"
            )
        stub.write_text(
            "import http.client,runpy\n"
            + redirect
            + f"runpy.run_path({str(usage_transport._CHILD)!r},run_name='__main__')\n"
        )
        started = time.monotonic_ns() - 7_800_000_000
        try:
            with pytest.raises(UsageReadFailed, match="TRANSPORT_TIMEOUT"):
                usage_transport._run(_child_message(started+9_000_000_000), started=started, child=stub)
        finally:
            stop.set()
            fixture.join(timeout=3)
        assert accepted.is_set() and not fixture.is_alive()
        assert time.monotonic_ns()-started < 10_500_000_000
