"""One fixed, isolated metadata HTTP operation, followed by bounded JSON parsing."""
import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from django.db import connections

from selahcue_api.apps.providers.configuration import get_provider_configuration
from selahcue_api.apps.providers.contracts import ProviderConfigurationError
from selahcue_api.apps.usage.observation_contracts import UsageFailureCode as Code, UsageReadFailed

from .grants_transport import _cleanup, _read_end, _read_frame, _write
from .usage_child import MAX_BODY, MAX_INPUT, MAX_OUTPUT, decode_b64, frame, invocation

_CHILD = Path(__file__).with_name("usage_child.py").resolve()
_MAX_BIGINT = (1 << 63) - 1


def invalid(code=Code.INVALID_RESPONSE):
    raise UsageReadFailed(code) from None


def _json_pairs(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        invalid()
    return obj


def _parse_int(value):
    if len(value.lstrip("-")) > 38 or len(value) > 128:
        invalid()
    return int(value)


def _parse_decimal(value):
    if len(value) > 128:
        invalid()
    _, sep, exponent = value.lower().partition("e")
    if sep and abs(int(exponent)) > 1000:
        invalid()
    return Decimal(value)


def _validate_scalars(value):
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, list):
        if len(value) > 1000:
            invalid()
        for member in value:
            _validate_scalars(member)
    elif isinstance(value, dict):
        for key, member in value.items():
            _validate_scalars(key)
            _validate_scalars(member)


def metadata_json(body):
    if len(body) > MAX_BODY:
        invalid(Code.RESPONSE_TOO_LARGE)
    try:
        source = body.decode("utf-8")
        depth, quoted, escaped = 0, False, False
        for char in source:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > 16:
                    invalid()
            elif char in "]}":
                depth -= 1
        result = json.loads(
            source, object_pairs_hook=_json_pairs, parse_int=_parse_int,
            parse_float=_parse_decimal, parse_constant=lambda _: invalid(),
        )
        _validate_scalars(result)
        return object_value(result)
    except (ValueError, RecursionError, ArithmeticError):
        invalid()


def object_value(value):
    if type(value) is not dict:
        invalid()
    return value


def array_value(value):
    if type(value) is not list:
        invalid()
    return value


def optional_id(value):
    if value is None:
        return None
    if type(value) is not str or not 1 <= len(value) <= 256 or any(not 33 <= ord(c) <= 126 for c in value):
        invalid()
    return value


def counter(value, *, allow_decimal=False, maximum=_MAX_BIGINT):
    if allow_decimal and type(value) is Decimal:
        if 0 <= value <= maximum and value == value.to_integral_value():
            return int(value)
        invalid()
    if type(value) is not int or not 0 <= value <= maximum:
        invalid()
    return value


def exact_duration(value):
    if type(value) not in (int, Decimal):
        invalid()
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        invalid()
    if not amount:
        return Decimal(0)
    _, digits, exponent = amount.as_tuple()
    if len(digits) + exponent > 20:
        invalid()
    while exponent < -18 and digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    if exponent < -18:
        invalid()
    return Decimal((0, digits, exponent))


def _output(reply):
    if reply.get("schema_version") != 1 or type(reply.get("schema_version")) is not int:
        invalid(Code.TRANSPORT_ERROR)
    if set(reply) == {"schema_version", "kind", "status", "body_b64"} and reply["kind"] == "response":
        status = reply["status"]
        if type(status) is not int or status != 200:
            invalid(Code.TRANSPORT_ERROR)
        return decode_b64(reply["body_b64"], MAX_BODY)
    if set(reply) == {"schema_version", "kind", "code"} and reply["kind"] == "failure":
        if reply["code"] in ("CONNECT_TIMEOUT", "READ_TIMEOUT", "ABSOLUTE_TIMEOUT"):
            invalid(Code.TRANSPORT_TIMEOUT)
        if reply["code"] == "RESPONSE_TOO_LARGE":
            invalid(Code.RESPONSE_TOO_LARGE)
    invalid(Code.TRANSPORT_ERROR)


def _run(payload, *, started, child=None):
    io_deadline = started + 9_000_000_000
    final_deadline = started + 10_000_000_000
    encoded = frame(payload)
    if len(encoded) - 4 > MAX_INPUT or time.monotonic_ns() >= io_deadline:
        invalid(Code.TRANSPORT_TIMEOUT)
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", str(_CHILD if child is None else child)],
            shell=False, close_fds=True, start_new_session=True, bufsize=0,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
        )
    except OSError:
        invalid(Code.TRANSPORT_ERROR)
    finished = False
    try:
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        _write(process.stdin, encoded, io_deadline)
        response = _read_frame(process.stdout, MAX_OUTPUT, io_deadline)
        _read_end(process.stdout, io_deadline)
        finished = True
    except TimeoutError:
        invalid(Code.TRANSPORT_TIMEOUT)
    except (OSError, EOFError, ValueError, TypeError, RecursionError):
        pass
    finally:
        status = _cleanup(process, final_deadline, kill=not finished)
    if status == -signal.SIGALRM or time.monotonic_ns() >= final_deadline:
        invalid(Code.TRANSPORT_TIMEOUT)
    if status or not finished:
        invalid(Code.TRANSPORT_ERROR)
    try:
        return _output(response)
    except (ValueError, TypeError):
        invalid(Code.TRANSPORT_ERROR)


def read_metadata(scope, interval, cursor, profile):
    if os.name != "posix":
        invalid(Code.CONFIG_UNAVAILABLE)
    try:
        config = get_provider_configuration(required_role="usage")
    except ProviderConfigurationError:
        invalid(Code.CONFIG_UNAVAILABLE)
    credentials = tuple(row for row in config.usage_credentials if row.scope == scope)
    if config.policy is None or not any(p.scope == scope for p in config.policy.scopes) or len(credentials) != 1:
        invalid(Code.SCOPE_MISSING)
    started = time.monotonic_ns()
    secret = credentials[0].secret.value
    if not 1 <= len(secret) <= 4096 or any(not 33 <= byte <= 126 for byte in secret):
        invalid(Code.CONFIG_UNAVAILABLE)
    if interval.start.microsecond or interval.end.microsecond:
        invalid()
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    second = timedelta(seconds=1)
    payload = {
        "schema_version": 1, "provider": scope.provider, "parent_scope_id": scope.parent_scope_id,
        "profile": profile, "start_time": (interval.start - epoch) // second,
        "end_time": (interval.end - epoch) // second, "cursor": cursor,
        "credential_b64": base64.b64encode(secret).decode("ascii"),
        "io_deadline_ns": started + 9_000_000_000,
    }
    try:
        invocation(payload)
    except (ValueError, TypeError):
        invalid(Code.INVALID_CURSOR if cursor is not None else Code.INVALID_RESPONSE)
    connections.close_all()
    return metadata_json(_run(payload, started=started))
