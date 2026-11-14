"""Run the API's production WSGI command against synthetic local settings."""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from http.client import HTTPConnection
from http.cookies import SimpleCookie
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


# The parent test suite snapshots the seeded catalogue in an autouse fixture.
# The subprocess itself never connects to that database.
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(os.name != "posix", reason="Gunicorn requires POSIX"),
]
API_ROOT = Path(__file__).resolve().parents[1]
CSRF_PATH = "/graphql/csrf"


@pytest.fixture
def process_directory():
    # Unix-domain sockets have a short path limit. The runner's pytest temp
    # path can already exceed it on macOS.
    with TemporaryDirectory(prefix="selahcue-api-", dir="/tmp") as directory:
        root = Path(directory)
        (root / "home").mkdir()
        (root / "runtime").mkdir()
        yield root


@contextmanager
def gunicorn_process(process_directory, **settings):
    executable = Path(sys.executable).with_name("gunicorn")
    assert executable.is_file(), "Gunicorn is missing from the locked API environment"
    config = API_ROOT / "gunicorn.conf.py"
    command = [
        str(executable),
        "--config",
        str(config),
        "--bind",
        "127.0.0.1:0",
        "selahcue_api.wsgi:application",
    ]
    # Omit the host's proxy, application and credential environment entirely.
    environment = {
        "HOME": str(process_directory / "home"),
        "XDG_RUNTIME_DIR": str(process_directory / "runtime"),
        "TMPDIR": str(process_directory),
        "ENVIRONMENT": "prod",
        "SECRET_KEY": "synthetic-key-for-local-gunicorn-process-tests-only",
        "SQL_ENGINE": "django.db.backends.postgresql",
        "SQL_HOST": str(process_directory / "unused-postgres-socket"),
        "SQL_PASSWORD": "synthetic-password-unused-by-csrf-bootstrap",
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1",
        "SECURE_HSTS_SECONDS": "60",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    environment.update(settings)
    log_path = process_directory / "gunicorn.log"
    with log_path.open("wb") as output:
        process = subprocess.Popen(
            command,
            cwd=API_ROOT,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            yield process, log_path
        finally:
            # Also clean up the entire process group on a test failure or timeout.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)


def local_request(port, *, method="GET", path=CSRF_PATH, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.headers, response.read()
    finally:
        connection.close()


def wait_for_csrf(process, log_path):
    deadline = time.monotonic() + 15
    while process.poll() is None and time.monotonic() < deadline:
        log = log_path.read_text()
        endpoint = re.search(r"Listening at: http://127\.0\.0\.1:(\d+)", log)
        if endpoint:
            port = int(endpoint[1])
            try:
                status, headers, body = local_request(port)
            except OSError:
                pass
            else:
                assert status == 200
                assert json.loads(body) == {"ready": True}
                return port, headers
        time.sleep(0.05)
    pytest.fail(f"Gunicorn did not serve the CSRF route:\n{log_path.read_text()}")


def test_serves_csrf_and_shuts_down_without_orphan_workers(process_directory):
    with gunicorn_process(process_directory) as (process, log_path):
        _, headers = wait_for_csrf(process, log_path)
        assert headers["Cache-Control"] == "no-store"
        cookie = SimpleCookie(headers["Set-Cookie"])["csrftoken"]
        assert cookie["secure"]

        process.terminate()
        assert process.wait(timeout=10) == 0, log_path.read_text()
        with pytest.raises(ProcessLookupError):
            os.killpg(process.pid, 0)


def test_preserves_existing_control_socket(process_directory):
    socket_path = process_directory / "runtime" / "gunicorn.ctl"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(socket_path))
        listener.listen()
        existing_identity = socket_path.stat().st_ino

        with gunicorn_process(process_directory) as (process, log_path):
            wait_for_csrf(process, log_path)
            process.terminate()
            assert process.wait(timeout=10) == 0, log_path.read_text()

        assert socket_path.exists(), "Gunicorn removed another process's control socket"
        assert socket_path.stat().st_ino == existing_identity


def test_missing_production_secret_prevents_server_boot(process_directory):
    with gunicorn_process(process_directory, SECRET_KEY="") as (process, log_path):
        assert process.wait(timeout=15) != 0
        assert "SECRET_KEY must be set when ENVIRONMENT='prod'" in log_path.read_text()


@pytest.mark.parametrize(("trust_forwarded_proto", "expected_hsts"), [("0", None), ("1", "max-age=60")])
def test_only_django_opt_in_accepts_forwarded_https(process_directory, trust_forwarded_proto, expected_hsts):
    with gunicorn_process(
        process_directory,
        SELAHCUE_TRUST_FORWARDED_PROTO=trust_forwarded_proto,
        SECURE_HSTS_INCLUDE_SUBDOMAINS="0",
        SECURE_HSTS_PRELOAD="0",
    ) as (process, log_path):
        port, headers = wait_for_csrf(process, log_path)
        assert headers["Strict-Transport-Security"] is None

        status, headers, _ = local_request(port, headers={"X-Forwarded-Proto": "https"})
        assert status == 200
        assert headers["Strict-Transport-Security"] == expected_hsts


def test_invalid_graphql_request_canaries_are_absent_from_logs(process_directory):
    query_secret = "synthetic-secret-in-query-a37e9c"
    body_secret = "synthetic-secret-in-body-c91b5d"
    with gunicorn_process(process_directory) as (process, log_path):
        port, headers = wait_for_csrf(process, log_path)
        token = SimpleCookie(headers["Set-Cookie"])["csrftoken"].value

        status, _, _ = local_request(
            port,
            method="POST",
            path=f"/graphql/account?token={query_secret}",
            body=body_secret,
            headers={
                "Content-Type": "application/json",
                "Cookie": f"csrftoken={token}",
                "X-CSRFToken": token,
            },
        )
        assert status == 400

        process.terminate()
        assert process.wait(timeout=10) == 0, log_path.read_text()
        log = log_path.read_text()
        assert query_secret not in log
        assert body_secret not in log
