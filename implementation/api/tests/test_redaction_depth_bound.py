"""Audit-payload redaction is depth-bounded (86ak1090r, AC 9).

`redact_public_payload` and `assert_no_restricted_payload_fields` used to recurse with no
bound, so a deeply nested `extra_before` / `extra_after` raised `RecursionError` from inside
the licence state machine's row lock. On the success path that rolls back and is safe; on the
refusal path it destroys the DENIED audit row, the same defect class as the over-long
`source_surface` finding on 86ak5mn00.

These tests are pure functions, no database: the bound is a property of the two functions
and of the writer's boundary check, which the main slice file exercises with a real licence.
"""

from __future__ import annotations

import contextlib
import signal

import pytest

from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.graphql.redaction import (
    MAX_PAYLOAD_CONTAINERS,
    MAX_PAYLOAD_DEPTH,
    assert_no_restricted_payload_fields,
    ensure_payload_depth,
    redact_public_payload,
)


@contextlib.contextmanager
def _must_finish_within(seconds: int):
    """Turn "an unbounded walk" into a failing test instead of a hung one.

    A walker with no bound on a self-referential payload does not fail, it never returns, so
    a mutant that removes the bound would stall the suite rather than turn it red. SIGALRM is
    Unix-only; elsewhere the guard is absent and the bound itself is what is tested.
    """
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def on_alarm(signum, frame):
        raise TimeoutError(f"did not finish within {seconds}s: the walk is unbounded")

    previous = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _nested_dict(levels: int, leaf="leaf"):
    """`levels` mappings deep: levels=1 is {"k": leaf}."""
    value = leaf
    for _ in range(levels):
        value = {"k": value}
    return value


def _nested_list(levels: int, leaf="leaf"):
    value = leaf
    for _ in range(levels):
        value = [value]
    return value


# The functions touch no database. The mark is for the suite's session-wide catalogue
# snapshot fixture (conftest.py), which needs the test database to exist even for a test that
# never queries it.
pytestmark = pytest.mark.django_db

MAX_CONTAINERS_MINUS_ONE = MAX_PAYLOAD_CONTAINERS - 2  # the list itself is one container

PATHOLOGICAL = 5000  # far past CPython's default recursion limit of 1000


def test_the_bound_is_a_small_positive_number():
    """Real audit payloads are flat (a status, a date, an id). A bound in the hundreds would
    defeat the point; one of 1 would refuse a legitimate nested object."""
    assert 2 <= MAX_PAYLOAD_DEPTH <= 32


@pytest.mark.parametrize("builder", [_nested_dict, _nested_list], ids=["dicts", "lists"])
def test_a_payload_exactly_at_the_bound_still_passes_every_function(builder):
    payload = builder(MAX_PAYLOAD_DEPTH)
    ensure_payload_depth(payload)
    redact_public_payload(payload)
    assert_no_restricted_payload_fields(payload)


@pytest.mark.parametrize("builder", [_nested_dict, _nested_list], ids=["dicts", "lists"])
def test_a_payload_one_past_the_bound_is_refused_by_every_function(builder):
    payload = builder(MAX_PAYLOAD_DEPTH + 1)
    for function in (ensure_payload_depth, redact_public_payload, assert_no_restricted_payload_fields):
        with pytest.raises(SafeAPIError) as raised:
            function(payload)
        assert raised.value.code == ErrorCode.VALIDATION_FAILED, function.__name__


@pytest.mark.parametrize("builder", [_nested_dict, _nested_list], ids=["dicts", "lists"])
def test_a_pathological_payload_is_refused_not_a_recursion_error(builder):
    payload = builder(PATHOLOGICAL)
    for function in (ensure_payload_depth, redact_public_payload, assert_no_restricted_payload_fields):
        # `pytest.raises(SafeAPIError)` alone would let a RecursionError through as a failure,
        # which is the point: only the coded refusal is acceptable.
        with pytest.raises(SafeAPIError) as raised:
            function(payload)
        assert raised.value.code == ErrorCode.VALIDATION_FAILED, function.__name__


def test_a_self_referential_payload_is_refused():
    cyclic: dict = {}
    cyclic["again"] = cyclic
    for function in (ensure_payload_depth, redact_public_payload, assert_no_restricted_payload_fields):
        with _must_finish_within(10), pytest.raises(SafeAPIError) as raised:
            function(cyclic)
        assert raised.value.code == ErrorCode.VALIDATION_FAILED, function.__name__


def test_a_wide_self_referential_payload_is_refused_promptly():
    """Depth alone is not enough: a mapping with many references to itself has about
    `width ** MAX_PAYLOAD_DEPTH` paths below the depth bound, so refusing it by depth alone
    would take effectively forever. The container cap is what makes the refusal prompt."""
    wide: dict = {}
    for index in range(40):
        wide[f"again{index}"] = wide
    for function in (ensure_payload_depth, redact_public_payload, assert_no_restricted_payload_fields):
        with _must_finish_within(10), pytest.raises(SafeAPIError) as raised:
            function(wide)
        assert raised.value.code == ErrorCode.VALIDATION_FAILED, function.__name__


def test_a_wide_but_shallow_payload_is_not_refused():
    """The container cap counts containers, not scalars: a long flat list is fine."""
    ensure_payload_depth({"ids": list(range(100_000)), "tags": ["a"] * 50_000})
    ensure_payload_depth([{"k": index} for index in range(MAX_CONTAINERS_MINUS_ONE)])


def test_mixed_nesting_counts_both_kinds_of_container():
    mixed = {"a": [{"b": [{"c": [{"d": [{"e": [{"f": [{"g": [{"h": ["leaf"]}]}]}]}]}]}]}]}
    assert MAX_PAYLOAD_DEPTH < 16  # the literal above is 16 containers deep (8 dicts, 8 lists)
    with pytest.raises(SafeAPIError):
        ensure_payload_depth(mixed)


def test_the_bound_does_not_change_what_redaction_does_to_an_ordinary_payload():
    """Positive control for the redaction itself, so the bound cannot be 'passing' by the
    functions having been emptied."""
    payload = {"status": "REVOKED", "nested": {"full_key": "SC-SECRET", "ok": [1, {"token": "t"}]}}
    redacted = redact_public_payload(payload)
    assert redacted["nested"]["full_key"] == "[redacted]"
    assert redacted["status"] == "REVOKED"
    assert redacted["nested"]["ok"][0] == 1
    assert_no_restricted_payload_fields(redacted)
    with pytest.raises(SafeAPIError):
        assert_no_restricted_payload_fields(payload)


def test_strings_and_bytes_are_leaves_not_containers():
    """A long string is a Sequence in Python; treating it as one would recurse per character."""
    ensure_payload_depth({"s": "x" * 100_000, "b": b"y" * 100_000})
    redact_public_payload({"s": "x" * 100_000})
    assert_no_restricted_payload_fields({"s": "x" * 100_000})
