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
