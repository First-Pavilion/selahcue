"""Offline tests of the anonymous verifier's byte and process boundaries."""

from collections import deque
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from functools import partial
import io
import os
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from _installer_publication_fixtures import ARTIFACTS, VERSION, digest
from installer_publication import public_verify
from installer_publication.contracts import (
    ObjectPlan, PublicationError, PublicPlan, derive_object, parse_verification, record_bytes,
)

_BODY = b"synthetic installer bytes"
_OBJ = derive_object("windows", VERSION, ARTIFACTS["windows"][0], len(_BODY), digest(_BODY))
_MARKER = "synthetic-credential-never-pass-to-verifier"


def _response(obj=_OBJ, body=_BODY, *, status=200, remove=(), extra=()):
    headers = (
        ("Content-Length", str(obj.size_bytes)),
        ("Content-Type", obj.content_type),
        ("Content-Disposition", obj.content_disposition),
        ("Cache-Control", "immutable, public, max-age=31536000"),
    )
    lines = [f"HTTP/1.1 {status} Fixture\r\n"]
    lines.extend(f"{name}: {value}\r\n" for name, value in (*headers, *extra) if name not in remove)
    return ("".join(lines) + "\r\n").encode("ascii") + body


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(2)
        with self.request.makefile("rb") as wire:
            request = bytearray()
            while line := wire.readline(4096 - len(request)):
                request.extend(line)
                if line == b"\r\n":
                    self.server.requests.append(bytes(request))
                    self.request.sendall(self.server.responses.popleft())
                    break


@contextmanager
def _loopback(*responses):
    with socketserver.TCPServer(("127.0.0.1", 0), _Handler) as server:
        server.responses = deque(responses)
        server.requests = []
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=2)


def _loopback_connector(address, deadline, clock):
    return socket.create_connection(address, timeout=min(2, deadline - clock()))


class _Clock:
    now = 0.0

    def __call__(self):
        return self.now


class _Socket:
    def __init__(self, response, *, clock=None, slow=False, failure=False):
        self.wire = io.BytesIO(response)
        self.header_size = response.index(b"\r\n\r\n") + 4
        self.clock = clock
        self.slow = slow
        self.failure = failure
        self.body_limit = 0
        self.timeouts = []

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.wire.close()

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def sendall(self, request):
        self.request = request

    def recv(self, size):
        if self.wire.tell() >= self.header_size:
            self.body_limit = max(self.body_limit, size)
            if self.failure and self.body_read >= 2:
                raise TimeoutError("unsafe transport detail")
            if self.slow:
                self.clock.now += 59.0
                size = min(size, 1)
            elif self.failure:
                size = min(size, 2)
            data = self.wire.read(size)
            self.body_read += len(data)
            return data
        data = self.wire.read(min(size, self.header_size - self.wire.tell()))
        self.body_read = 0
        return data


class PublicVerifyTests(unittest.TestCase):
    def _verify(self, obj, connector, clock=None):
        return public_verify._verify_object(obj, connector, clock or _Clock())

    def _assert_mismatch(self, obj, response):
        with _loopback(response) as server:
            with self.assertRaises(PublicationError) as error:
                self._verify(obj, partial(_loopback_connector, server.server_address))
        self.assertEqual(error.exception.exit_code, 3)
        self.assertEqual(len(server.requests), 1)

    def test_exact_full_bytes_headers_and_eof_required(self):
        with _loopback(_response()) as server:
            observed = self._verify(_OBJ, partial(_loopback_connector, server.server_address))
        self.assertEqual(observed.observed_size_bytes, len(_BODY))
        self.assertEqual(observed.observed_sha256, digest(_BODY))
        self.assertEqual(observed.headers.content_length, len(_BODY))
        self.assertIsNone(observed.headers.content_encoding)
        request, = server.requests
        self.assertTrue(request.startswith(b"GET /installers/1.2.3-rc.1%2Bsynthetic/"))
        self.assertIn(b"Operator%20Setup.exe HTTP/1.1\r\n", request)
        self.assertIn(b"\r\nAccept-Encoding: identity\r\n", request)
        for blocked in (b"authorization:", b"proxy-authorization:", b"cookie:", b"range:", b"\r\nif-"):
            self.assertNotIn(blocked, request.lower())

        for name, response in {
            "equal length wrong bytes": _response(body=b"x" * len(_BODY)),
            "premature EOF": _response(body=_BODY[:-1]),
            "extra byte after valid declared body": _response(body=_BODY + b"!"),
            "no length": _response(remove=("Content-Length",)),
            "wrong length": _response(
                extra=(("content-length", str(len(_BODY) - 1)),), remove=("Content-Length",),
            ),
            "wrong MIME and charset": _response(
                extra=(("content-type", "text/html; charset=UTF-8"),), remove=("Content-Type",),
            ),
            "wrong filename": _response(
                extra=(("content-disposition", 'attachment; filename="Other.exe"'),), remove=("Content-Disposition",),
            ),
            "wrong cache": _response(
                extra=(("cache-control", "private"),), remove=("Cache-Control",),
            ),
        }.items():
            with self.subTest(name=name):
                self._assert_mismatch(_OBJ, response)
        for body in (b"<!doctype html><title>Error</title>", b"<?xml version='1.0'?><Error />"):
            with self.subTest(body=body):
                obj = derive_object("windows", VERSION, _OBJ.filename, len(body), digest(body))
                self._assert_mismatch(obj, _response(obj, body))

    def test_redirect_auth_encoding_and_duplicate_headers_refused(self):
        for label, response in {
            "redirect": _response(status=302, extra=(("Location", "https://invalid.example.test/elsewhere"),)),
            "challenge": _response(status=401, extra=(("WWW-Authenticate", "Basic"),)),
            "auth header on nominal success": _response(extra=(("WWW-Authenticate", "Basic"),)),
            "encoding": _response(extra=(("Content-Encoding", "identity"),)),
            "duplicate length": _response(extra=(("content-length", str(_OBJ.size_bytes)),)),
            "conflicting critical header": _response(extra=(("content-type", "text/xml"),)),
            "conflicting framing": _response(extra=(("Transfer-Encoding", "chunked"),)),
            "partial": _response(status=206),
        }.items():
            with self.subTest(label=label):
                self._assert_mismatch(_OBJ, response)

    def test_size_plus_one_and_total_deadline_are_bounded(self):
        body = b"x" * (1024 * 1024 + 10)
        obj = derive_object("windows", VERSION, _OBJ.filename, len(body), digest(body))
        stream = _Socket(_response(obj, body + b"!surplus"))
        with self.assertRaises(PublicationError) as error:
            self._verify(obj, lambda deadline, clock: stream)
        self.assertEqual(error.exception.exit_code, 3)
        self.assertEqual(stream.body_read, obj.size_bytes + 1)
        self.assertEqual(stream.body_limit, 1024 * 1024)

        clock = _Clock()
        body = bytes(range(100))
        obj = derive_object("windows", VERSION, _OBJ.filename, len(body), digest(body))
        stream = _Socket(_response(obj, body), clock=clock, slow=True)
        deadlines = []

        def connect(deadline, _):
            deadlines.append(deadline)
            return stream

        with self.assertRaises(PublicationError) as error:
            self._verify(obj, connect, clock)
        self.assertEqual(error.exception.exit_code, 4)
        self.assertEqual(deadlines, [30.0])
        self.assertEqual(max(stream.timeouts), 60.0)
        self.assertLess(stream.body_read, len(body))
        self.assertGreaterEqual(clock.now, 3600.0)

    def test_retry_restarts_hash_and_has_finite_attempts(self):
        first = _Socket(_response(), failure=True)
        second = _Socket(_response(status=503))
        final = _Socket(_response())
        attempts = iter((first, second, final))
        verified = self._verify(_OBJ, lambda *_: next(attempts))
        self.assertEqual(verified.observed_sha256, digest(_BODY))
        self.assertEqual(verified.observed_size_bytes, len(_BODY))
        self.assertEqual(first.body_read, 2)
        for stream in (first, second, final):
            self.assertNotIn(b"\r\nrange:", stream.request.lower())

        deadlines = []

        def fail(deadline, _):
            deadlines.append(deadline)
            raise TimeoutError(_MARKER)

        with self.assertRaises(PublicationError) as error:
            self._verify(_OBJ, fail)
        self.assertEqual(error.exception.exit_code, 4)
        self.assertNotIn(_MARKER, str(error.exception))
        self.assertEqual(deadlines, [30.0] * 3)

    def test_same_host_child_has_no_credentials_or_ambient_sdk(self):
        scripts = str(Path(__file__).resolve().parent)
        parent_pid = os.getpid()
        child_source = """
import os, sys
# Python/macOS synthesize locale entries even with an empty exec environment.
assert set(os.environ) <= {{'LC_CTYPE', '__CF_USER_TEXT_ENCODING'}}, sorted(os.environ)
assert os.getpid() != {parent_pid}
sys.path.insert(0, {scripts!r})
from installer_publication import public_verify
from functools import partial
from test_installer_publication_verify import _loopback_connector
public_verify._connect_https = partial(_loopback_connector, {address!r})
status = public_verify.worker_main()
assert not any(name.split('.')[0] in ('boto3', 'botocore', 'awscli') for name in sys.modules)
raise SystemExit(status)
"""
        secrets = dict.fromkeys((
            "INSTALLER_S3_ACCESS_KEY", "INSTALLER_S3_SECRET_KEY", "AWS_SESSION_TOKEN",
            "AWS_PROFILE", "SPACES_ACCESS_KEY_ID", "SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE",
            "OPENAI_API_KEY", "HTTPS_PROXY", "PYTHONPATH",
        ), _MARKER)
        with _loopback(_response()) as server:
            test_argv = [sys.executable, "-I", "-S", "-c", child_source.format(
                scripts=scripts, parent_pid=parent_pid, address=server.server_address,
            )]
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, secrets), redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertNotIn(_MARKER, str(public_verify._child_argv()))
                with self.assertRaises(PublicationError) as error:
                    public_verify.verify_object(_OBJ)
                self.assertEqual(error.exception.exit_code, 3)
                self.assertNotIn(_MARKER, str(error.exception))
                with patch.object(public_verify, "_child_argv", return_value=test_argv):
                    result = public_verify.verify_object_in_child(_OBJ)
        self.assertEqual(result.observed_sha256, digest(_BODY))
        self.assertEqual(len(server.requests), 1)
        for output in (stdout.getvalue(), stderr.getvalue(), str(test_argv), str(result), str(server.requests)):
            self.assertNotIn(_MARKER, output)

    def test_public_plan_observes_every_object_in_order(self):
        objects = tuple(derive_object(identifier, VERSION, filename, len(_BODY), digest(_BODY))
                        for identifier, (filename, _, _) in ARTIFACTS.items())
        plan = PublicPlan(1, "synthetic-release", VERSION, "a" * 40, objects)
        with _loopback(*(_response(obj) for obj in objects)) as server:
            with patch.dict(os.environ, clear=True), patch.object(
                public_verify, "_connect_https", partial(_loopback_connector, server.server_address),
            ):
                receipt = public_verify.verify_public_plan(plan)
        self.assertEqual(receipt, parse_verification(record_bytes(receipt)))
        self.assertEqual(receipt.plan_sha256, digest(record_bytes(plan)))
        self.assertEqual([result.url for result in receipt.objects], [obj.url for obj in objects])
        self.assertEqual(len(server.requests), 3)

        with _loopback(_response(objects[0]), _response(objects[1], body=b"wrong")) as server:
            with patch.dict(os.environ, clear=True), patch.object(
                public_verify, "_connect_https", partial(_loopback_connector, server.server_address),
            ):
                with self.assertRaises(PublicationError) as error:
                    public_verify.verify_public_plan(plan)
        self.assertIn("universalMac", error.exception.reason)
        self.assertEqual(len(server.requests), 2)

    def test_child_protocol_bounds_and_redacts_bad_output(self):
        for statement, code in (
            (f"print({_MARKER!r}, file=sys.stderr); sys.exit(3)", 3),
            (f"print({_MARKER!r}); sys.exit(0)", 5),
            ("sys.stdout.buffer.write(b'x' * (1024 * 1024 + 2)); sys.stdout.flush(); time.sleep(5)", 5),
            ("time.sleep(5)", 4),
        ):
            with self.subTest(statement=statement), patch.object(public_verify, "_child_argv",
                return_value=[sys.executable, "-I", "-S", "-c", "import sys,time; " + statement],
            ), patch.object(public_verify, "_TOTAL_TIMEOUT", 1.0):
                with self.assertRaises(PublicationError) as error:
                    public_verify.verify_object_in_child(_OBJ)
                self.assertEqual(error.exception.exit_code, code)
                self.assertNotIn(_MARKER, str(error.exception))

    def test_caller_deadline_validation_never_launches_expired_or_invalid_child(self):
        for deadline, code in ((float("nan"), 2), (float("inf"), 2), (True, 2), ("123", 2), (10**400, 2),
                               (time.monotonic() - 1, 4)):
            with self.subTest(deadline=deadline), patch.object(public_verify.subprocess, "Popen") as spawn:
                with self.assertRaises(PublicationError) as error:
                    public_verify.verify_object_in_child(_OBJ, deadline=deadline)
                self.assertEqual(error.exception.exit_code, code)
                spawn.assert_not_called()

    def test_caller_deadline_shortens_child_and_cannot_extend_own_cap(self):
        for own_cap, caller_remaining in ((10.0, 0.15), (0.15, 10.0)):
            children = []
            original = subprocess.Popen
            def spawn(*args, **kwargs):
                child = original(*args, **kwargs); children.append(child); return child
            with patch.object(public_verify, "_TOTAL_TIMEOUT", own_cap), patch.object(
                public_verify, "_child_argv", return_value=[sys.executable, "-I", "-S", "-c",
                                                           "import time; time.sleep(5)"],
            ), patch.object(public_verify.subprocess, "Popen", side_effect=spawn):
                started = time.monotonic()
                with self.assertRaises(PublicationError) as error:
                    public_verify.verify_object_in_child(_OBJ, deadline=started + caller_remaining)
                self.assertEqual(error.exception.exit_code, 4)
                self.assertLess(time.monotonic() - started, 2)
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].returncode)

    def test_invalid_child_input_never_opens_public_connection(self):
        argv = public_verify._child_argv()
        bad_inputs = (b"x" * (1024 * 1024 + 1), record_bytes(
            ObjectPlan(_OBJ.id, _OBJ.key, "https://invalid.example.test/", _OBJ.filename,
                       _OBJ.size_bytes, _OBJ.sha256, _OBJ.content_type, _OBJ.content_disposition, _OBJ.cache_control)
        ))
        for raw in bad_inputs:
            with self.subTest(size=len(raw)):
                result = subprocess.run(argv, input=raw, capture_output=True, env={}, timeout=3)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
