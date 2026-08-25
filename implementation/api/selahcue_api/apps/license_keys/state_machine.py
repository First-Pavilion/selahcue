"""The licence lifecycle state machine — the single normative model (FR-501).

Everything that changes `AppLicenseKey.status` goes through
`apply_license_status_transition`. That function is the only audited writer: it consults
`LEGAL_TRANSITIONS` below, refuses anything absent from it with a coded error, and writes
exactly one audit row per outcome (FR-508, NFR-506).

The individual mutations — revoke/extend (86ak1090r), the expiry job (86ak109dv),
suspend/reinstate (86ak5mn0c), conversion (86ak5mn2k), archiving (86ak5mn2m) — live in
their own tickets and write THROUGH this module. They must not assign `.status` directly;
a raw write skips the table, the audit row and the prior-status bookkeeping at once.

Reading of the PRD's exhaustive transition list
--------------------------------------------------------------------------------------
`docs/product/prds/SelahCue-Platform-PRD.md` §13 lists the legal transitions and closes
with "REVOKED and ARCHIVED are otherwise terminal". Two of its clauses — "any
non-terminal → SUSPENDED" and "any → REVOKED" — are wider than the terminality sentence
allows, so the reading is recorded here rather than left to whoever reads the table next:

* **Terminality is the tie-breaker.** A status named terminal has only the outbound edges
  the list spells out for it *by name*. REVOKED therefore keeps exactly one exit
  (REVOKED → ARCHIVED, from "EXPIRED/REVOKED/CONVERTED → ARCHIVED") and ARCHIVED has
  none — ARCHIVED → REVOKED is refused in spite of the literal "any → REVOKED", because
  un-archiving a licence into a kill state is not a lifecycle the PRD describes anywhere.
* **CONVERTED is not named terminal**, so "any non-terminal → SUSPENDED" reaches it and
  CONVERTED → SUSPENDED is legal. It is an odd licence to suspend (the key is already
  superseded), but the list is exhaustive and names only two terminal statuses.

Reinstatement (DEC-010 / FR-510)
--------------------------------------------------------------------------------------
`SUSPENDED → its prior status` is a transition to *stored data*, never to a constant.
`PRIOR_STATUS` is the sentinel that stands for it in the table, and it resolves against
`AppLicenseKey.prior_status`, which this module writes when the licence enters SUSPENDED
and clears when it leaves. A suspended licence with no recorded prior status is refused,
not defaulted to ACTIVATED — guessing would silently promote an EXPIRING licence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Union

from django.db import transaction

from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.graphql.context import ActorContext, require_reason
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


class PriorStatusTarget(Enum):
    """Sentinel for "return to the status recorded at suspension time" (DEC-010).

    An `Enum` rather than a bare object so it is hashable, comparable, has a readable
    repr in audit payloads and test failures, and cannot be confused with a
    `LicenseKeyStatus` by an `isinstance` check.
    """

    PRIOR_STATUS = "PRIOR_STATUS"


PRIOR_STATUS = PriorStatusTarget.PRIOR_STATUS

TransitionTarget = Union[LicenseKeyStatus, PriorStatusTarget]


# Terminal per PRD §13 — these two have only the outbound edges named for them explicitly.
TERMINAL_STATUSES: frozenset[LicenseKeyStatus] = frozenset(
    {LicenseKeyStatus.REVOKED, LicenseKeyStatus.ARCHIVED}
)

# Written at row creation by staff issuance (`services.generate_license_key`), not reached
# by any transition. The sweep in tests/test_license_state_machine.py treats a seed status
# as having a writer; every other status has to be a target in the table below.
SEED_STATUSES: frozenset[LicenseKeyStatus] = frozenset({LicenseKeyStatus.ISSUED})


# THE table. The only declaration of what is legal; nothing else may hold a second copy.
LEGAL_TRANSITIONS: dict[LicenseKeyStatus, frozenset[TransitionTarget]] = {
    LicenseKeyStatus.ISSUED: frozenset(
        {
            LicenseKeyStatus.ACTIVATED,  # first activation (devices/services.py)
            LicenseKeyStatus.EXPIRING,  # renewal-notice window, FR-502
            LicenseKeyStatus.SUSPENDED,  # FR-504
            LicenseKeyStatus.REVOKED,  # FR-505
        }
    ),
    LicenseKeyStatus.ACTIVATED: frozenset(
        {
            LicenseKeyStatus.EXPIRING,  # FR-502
            LicenseKeyStatus.SUSPENDED,  # FR-504
            LicenseKeyStatus.REVOKED,  # FR-505
            LicenseKeyStatus.CONVERTED,  # FR-506
        }
    ),
    LicenseKeyStatus.EXPIRING: frozenset(
        {
            LicenseKeyStatus.ACTIVATED,  # renewal, FR-509
            LicenseKeyStatus.EXPIRED,  # clock, FR-503
            LicenseKeyStatus.SUSPENDED,  # FR-504
            LicenseKeyStatus.REVOKED,  # FR-505
            LicenseKeyStatus.CONVERTED,  # FR-506
        }
    ),
    LicenseKeyStatus.EXPIRED: frozenset(
        {
            LicenseKeyStatus.ACTIVATED,  # late renewal, FR-509
            LicenseKeyStatus.SUSPENDED,  # FR-504
            LicenseKeyStatus.REVOKED,  # FR-505
            LicenseKeyStatus.ARCHIVED,  # retention hygiene, FR-507
        }
    ),
    LicenseKeyStatus.SUSPENDED: frozenset(
        {
            PRIOR_STATUS,  # reinstatement, FR-510 — resolves to stored data
            LicenseKeyStatus.REVOKED,  # FR-505
        }
    ),
    LicenseKeyStatus.CONVERTED: frozenset(
        {
            LicenseKeyStatus.SUSPENDED,  # FR-504 — CONVERTED is not a terminal status
            LicenseKeyStatus.REVOKED,  # FR-505
            LicenseKeyStatus.ARCHIVED,  # FR-507
        }
    ),
    LicenseKeyStatus.REVOKED: frozenset({LicenseKeyStatus.ARCHIVED}),  # FR-507; otherwise terminal
    LicenseKeyStatus.ARCHIVED: frozenset(),  # terminal
}

# Compile-time premise: the table must cover the enum exhaustively. A ninth status added
# without a row here would otherwise reach `LEGAL_TRANSITIONS[before]` and raise KeyError
# deep inside a transaction rather than being caught at import.
assert set(LEGAL_TRANSITIONS) == set(LicenseKeyStatus), (
    "LEGAL_TRANSITIONS must name every LicenseKeyStatus; missing: "
    f"{sorted(status.value for status in set(LicenseKeyStatus) - set(LEGAL_TRANSITIONS))}"
)
# Compile-time premise: terminality means what the docstring above says it means. ARCHIVED
# is a sink, and REVOKED's only exit is retention hygiene. Widening either — e.g. adding
# ARCHIVED -> ACTIVATED to "fix" a support ticket — has to break here first.
assert LEGAL_TRANSITIONS[LicenseKeyStatus.ARCHIVED] == frozenset(), (
    "ARCHIVED is terminal: it must have no outbound transitions"
)
assert LEGAL_TRANSITIONS[LicenseKeyStatus.REVOKED] == frozenset({LicenseKeyStatus.ARCHIVED}), (
    "REVOKED is terminal apart from ARCHIVED: it must have exactly one outbound transition"
)


# The statuses a licence can be suspended FROM, derived from the table rather than
# restated — a second hand-written list would drift. Reinstatement may only resolve to one
# of these, so a corrupted `prior_status` cannot promote a licence into a status that could
# never have been suspended in the first place.
SUSPENDABLE_SOURCES: frozenset[LicenseKeyStatus] = frozenset(
    source
    for source, targets in LEGAL_TRANSITIONS.items()
    if LicenseKeyStatus.SUSPENDED in targets
)


AUDIT_TARGET_TYPE = "app_license_key"
REFUSED_ACTION = "license_key.status_change_refused"
REINSTATE_ACTION = "license_key.reinstated"

# `AuditEvent.request_id` is CharField(max_length=128).
REQUEST_ID_MAX_LENGTH = 128


class IllegalLicenseTransition(SafeAPIError):
    """A transition absent from `LEGAL_TRANSITIONS` was attempted and refused.

    Carries `ErrorCode.CONFLICT` — the request conflicts with the current state of the
    resource, which is exactly what an illegal transition is. `detail` stays server-side:
    `SafeAPIError` sends only the generic safe message to the caller.
    """

    def __init__(
        self,
        *,
        from_status: LicenseKeyStatus,
        requested: TransitionTarget,
        detail: str,
    ) -> None:
        self.from_status = from_status
        self.requested = requested
        self.detail = detail
        super().__init__(ErrorCode.CONFLICT)


class _Refused(Exception):
    """Internal control flow: abandons the transaction so nothing is written, then the
    refusal audit row is recorded OUTSIDE it and the public error raised."""

    def __init__(self, *, before: LicenseKeyStatus, requested: TransitionTarget, detail: str) -> None:
        self.before = before
        self.requested = requested
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class LicenseTransitionResult:
    license_key: AppLicenseKey
    from_status: LicenseKeyStatus
    to_status: LicenseKeyStatus
    #: False when the licence already held the target status — an idempotent replay that
    #: writes neither a row change nor an audit event (NFR-506).
    changed: bool
    audit_event: AuditEvent | None


def legal_targets(from_status: LicenseKeyStatus) -> frozenset[TransitionTarget]:
    """The legal targets out of `from_status`, straight from the table."""
    return LEGAL_TRANSITIONS[LicenseKeyStatus(from_status)]


def is_legal_transition(from_status: LicenseKeyStatus, to_status: TransitionTarget) -> bool:
    """Whether the table permits this edge. Says nothing about idempotent replays, which
    are handled before legality is consulted."""
    return to_status in legal_targets(from_status)


def statuses_written_by_transition() -> frozenset[LicenseKeyStatus]:
    """Every status reachable as a transition target, derived from the table.

    `PRIOR_STATUS` resolves to a member of `SUSPENDABLE_SOURCES`, so it contributes those
    rather than a status of its own.
    """
    written: set[LicenseKeyStatus] = set()
    for targets in LEGAL_TRANSITIONS.values():
        for target in targets:
            if target is PRIOR_STATUS:
                written.update(SUSPENDABLE_SOURCES)
            else:
                written.add(target)
    return frozenset(written)


def statuses_without_writer(statuses: Iterable[Any] | None = None) -> frozenset[Any]:
    """The FR-501 sweep: statuses that no production code path can write.

    A status has a writer when it is either seeded at row creation or named as a target in
    `LEGAL_TRANSITIONS`. Defaults to the whole enum, so a ninth `LicenseKeyStatus` added
    without a writer is REPORTED here rather than quietly joining `EXPIRING` as a state the
    cascade consumes and nothing produces.

    `statuses` is a parameter so the sweep can be shown to bite: a test can hand it a status
    that has no writer and assert it comes back, which a self-referential
    `set(LicenseKeyStatus) - ...` check could never demonstrate.
    """
    candidates = set(LicenseKeyStatus) if statuses is None else set(statuses)
    return frozenset(candidates - set(SEED_STATUSES) - set(statuses_written_by_transition()))


def _default_action(to_status: LicenseKeyStatus, requested: TransitionTarget) -> str:
    """Audit action name. Reinstatement gets its own so suspend/reinstate pairs are
    reconstructible from the trail alone (FLOW-506), rather than looking like a plain
    move back to ACTIVATED/EXPIRING."""
    if requested is PRIOR_STATUS:
        return REINSTATE_ACTION
    return f"license_key.{to_status.value.lower()}"


def _coerce_status(value: Any) -> LicenseKeyStatus:
    try:
        return LicenseKeyStatus(value)
    except ValueError as error:
        # A status the enum no longer declares — a data problem, not a caller problem.
        raise SafeAPIError(ErrorCode.INTERNAL) from error


def _coerce_target(value: TransitionTarget | str) -> TransitionTarget:
    if isinstance(value, PriorStatusTarget):
        return value
    try:
        return LicenseKeyStatus(value)
    except ValueError as error:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED) from error


def _require_request_id(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned or len(cleaned) > REQUEST_ID_MAX_LENGTH:
        raise SafeAPIError(
            ErrorCode.VALIDATION_FAILED,
            f"A request id of 1-{REQUEST_ID_MAX_LENGTH} characters is required for every "
            "lifecycle transition.",
        )
    return cleaned


def _target_label(target: TransitionTarget) -> str:
    return target.value


def apply_license_status_transition(
    license_key: AppLicenseKey,
    *,
    to_status: TransitionTarget | str,
    actor: ActorContext,
    reason: str,
    request_id: str,
    action: str | None = None,
    source_surface: str = "admin_graphql",
    extra_before: dict[str, Any] | None = None,
    extra_after: dict[str, Any] | None = None,
) -> LicenseTransitionResult:
    """The one audited writer for `AppLicenseKey.status` (FR-501, FR-508, NFR-506).

    Pass `PRIOR_STATUS` as `to_status` to reinstate a suspended licence; the target is read
    from the row, never assumed.

    Outcomes, in the order they are decided:

    1. **Idempotent replay** — the licence already holds the target status. Nothing is
       written and no audit row is created; `changed` is False. Checked before legality so
       a second revoke of an already-REVOKED licence is a no-op rather than a refusal.
    2. **Refused** — the edge is absent from `LEGAL_TRANSITIONS`, or reinstatement was asked
       for with no usable recorded prior status. The status is unchanged, one DENIED audit
       row is written, and `IllegalLicenseTransition` (CONFLICT) is raised.
    3. **Applied** — status (and the prior-status bookkeeping) updated in one statement,
       and exactly one SUCCESS audit row written in the same transaction.

    Concurrency: the row is re-read under `select_for_update` and the decision is made on
    *that* value, so two racing callers cannot both see the pre-transition status and both
    write an audit row. (SQLite no-ops the lock; the race is only observable on Postgres,
    which is what `tests/test_concurrency_postgres.py` exists for.)

    Caveat worth knowing: the refusal audit row is written after this function's own
    `atomic()` block unwinds, so it survives on its own. A CALLER that wraps this in its
    own transaction and then lets `IllegalLicenseTransition` propagate will roll that row
    back with everything else — callers that need the denial durable must not swallow the
    transition inside a wider atomic block.
    """
    cleaned_reason = require_reason(reason)
    cleaned_request_id = _require_request_id(request_id)
    requested = _coerce_target(to_status)

    try:
        with transaction.atomic():
            locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)
            before = _coerce_status(locked.status)
            before_prior = locked.prior_status

            resolved = _resolve_target(before=before, prior_status=before_prior, requested=requested)

            if resolved == before:
                # Already in effect. No write, no second audit row.
                _sync(license_key, locked)
                return LicenseTransitionResult(
                    license_key=locked,
                    from_status=before,
                    to_status=before,
                    changed=False,
                    audit_event=None,
                )

            if not is_legal_transition(before, requested):
                raise _Refused(
                    before=before,
                    requested=requested,
                    detail=(
                        f"{before.value} -> {_target_label(requested)} is not a legal licence "
                        "transition"
                    ),
                )

            locked.status = resolved.value
            # Prior-status bookkeeping (DEC-010): recorded on the way IN to SUSPENDED, in the
            # same UPDATE as the status itself, and cleared on the way out so a stale value can
            # never be read by a later reinstatement.
            locked.prior_status = before.value if resolved is LicenseKeyStatus.SUSPENDED else ""
            locked.save(update_fields=["status", "prior_status", "updated_at"])

            event = record_audit_event(
                actor,
                action=action or _default_action(resolved, requested),
                target_type=AUDIT_TARGET_TYPE,
                target_id=str(locked.pk),
                request_id=cleaned_request_id,
                reason=cleaned_reason,
                source_surface=source_surface,
                result=AuditResult.SUCCESS,
                before={"status": before.value, "prior_status": before_prior, **(extra_before or {})},
                after={
                    "status": locked.status,
                    "prior_status": locked.prior_status,
                    **(extra_after or {}),
                },
            )
            _sync(license_key, locked)
            return LicenseTransitionResult(
                license_key=locked,
                from_status=before,
                to_status=resolved,
                changed=True,
                audit_event=event,
            )
    except _Refused as refused:
        # Outside the atomic block above: the transition rolled back, this row does not.
        record_audit_event(
            actor,
            action=REFUSED_ACTION,
            target_type=AUDIT_TARGET_TYPE,
            target_id=str(license_key.pk),
            request_id=cleaned_request_id,
            reason=cleaned_reason,
            source_surface=source_surface,
            result=AuditResult.DENIED,
            before={"status": refused.before.value},
            # The status did not move, so `after` reports the same status, plus what was asked
            # for. FR-508 wants before/after on every row, refusals included.
            after={
                "status": refused.before.value,
                "requested_status": _target_label(refused.requested),
            },
        )
        raise IllegalLicenseTransition(
            from_status=refused.before,
            requested=refused.requested,
            detail=refused.detail,
        ) from None


def _resolve_target(
    *,
    before: LicenseKeyStatus,
    prior_status: str,
    requested: TransitionTarget,
) -> LicenseKeyStatus:
    """Turn the requested target into a concrete status.

    Only `PRIOR_STATUS` needs resolving, and only from SUSPENDED. Refusing — rather than
    falling back to ACTIVATED — is the whole point of DEC-010: a licence suspended from
    EXPIRING must come back to EXPIRING or not at all.
    """
    if requested is not PRIOR_STATUS:
        return requested

    if before is not LicenseKeyStatus.SUSPENDED:
        raise _Refused(
            before=before,
            requested=requested,
            detail=f"{before.value} is not suspended, so it has no prior status to return to",
        )
    if not prior_status:
        raise _Refused(
            before=before,
            requested=requested,
            detail="no prior status was recorded at suspension time",
        )
    try:
        resolved = LicenseKeyStatus(prior_status)
    except ValueError:
        raise _Refused(
            before=before,
            requested=requested,
            detail=f"recorded prior status {prior_status!r} is not a licence status",
        ) from None
    if resolved not in SUSPENDABLE_SOURCES:
        raise _Refused(
            before=before,
            requested=requested,
            detail=(
                f"recorded prior status {resolved.value} is not a status a licence can be "
                "suspended from"
            ),
        )
    return resolved


def _sync(caller_instance: AppLicenseKey, locked: AppLicenseKey) -> None:
    """Copy the committed values back onto the caller's in-memory object.

    Without this the caller keeps a stale `.status` after a successful transition — the
    exact trap `tests/test_entitlement_manifest_slice.py` documents around first activation.
    """
    if caller_instance is locked:
        return
    caller_instance.status = locked.status
    caller_instance.prior_status = locked.prior_status
    caller_instance.updated_at = locked.updated_at
