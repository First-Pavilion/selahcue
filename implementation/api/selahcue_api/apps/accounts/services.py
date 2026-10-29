from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, timedelta
from datetime import timezone as dt_timezone
from enum import Enum

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone as djtz
from django.utils.crypto import salted_hmac
from django.utils.text import slugify

from selahcue_api.apps.accounts.models import (
    CredentialToken,
    CredentialTokenPurpose,
    CustomerOrg,
    CustomerRole,
    CustomerSession,
    CustomerSessionStatus,
    CustomerStatus,
    CustomerUser,
    CustomerUserStatus,
)
from selahcue_api.apps.audit.models import AuditResult
from selahcue_api.apps.audit.services import record_audit_event
# Safe at module scope: `throttling.guards` depends only on the cache, the pure limiter and
# the error enum — nothing in accounts — so this cannot close an import cycle.
from selahcue_api.apps.throttling.guards import (
    enforce_budget,
    enforce_budget_reporting_outage,
    spend_budget,
)
from selahcue_api.apps.throttling.services import BudgetOutcome, bucket_for_throttling
from selahcue_api.graphql.context import (
    ActorContext,
    ActorKind,
    StaffPermission,
    require_staff_permission,
    validate_idempotency_key,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreateCustomerData:
    idempotency_key: str
    name: str
    primary_contact_email: str
    country: str
    timezone: str
    status: str = CustomerStatus.PROSPECT
    plan: str = "TRIAL"
    seat_limit: int = 1
    billing_contact_email: str = ""
    internal_notes: str = ""


@dataclass(frozen=True)
class CreateCustomerResult:
    customer: CustomerOrg
    created: bool


def _validation_error() -> SafeAPIError:
    return SafeAPIError(ErrorCode.VALIDATION_FAILED)


def _clean_customer(customer: CustomerOrg) -> None:
    try:
        customer.full_clean()
    except ValidationError as error:
        raise _validation_error() from error


def _unique_slug(name: str) -> str:
    base = slugify(name)[:180] or "customer"
    candidate = base
    counter = 2
    while CustomerOrg.objects.filter(slug=candidate).exists():
        suffix = f"-{counter}"
        candidate = f"{base[: 220 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def create_customer(actor: ActorContext | None, data: CreateCustomerData) -> CreateCustomerResult:
    staff = require_staff_permission(actor, StaffPermission.MANAGE_CUSTOMERS)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    if data.seat_limit < 1:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    with transaction.atomic():
        existing = CustomerOrg.objects.filter(
            created_by_actor_id=staff.actor_id,
            idempotency_key=idempotency_key,
        ).first()
        if existing is not None:
            return CreateCustomerResult(customer=existing, created=False)

        try:
            status = CustomerStatus(data.status)
        except ValueError as error:
            raise _validation_error() from error

        customer = CustomerOrg(
            name=" ".join(data.name.strip().split()),
            slug=_unique_slug(data.name),
            status=status,
            primary_contact_email=data.primary_contact_email.strip().lower(),
            billing_contact_email=data.billing_contact_email.strip().lower(),
            country=data.country.strip().upper(),
            timezone=data.timezone.strip() or "UTC",
            plan=data.plan.strip().upper() or "TRIAL",
            seat_limit=data.seat_limit,
            internal_notes=data.internal_notes.strip(),
            created_by_actor_id=staff.actor_id,
            idempotency_key=idempotency_key,
        )
        _clean_customer(customer)
        # Concurrency-safe idempotency: two racing requests with the same
        # (actor, idempotency_key) both pass the check above; the unique constraint rejects the
        # loser's INSERT. Catch it in a savepoint and return the winner's row as an idempotent
        # replay instead of surfacing a spurious VALIDATION_FAILED. (Mirrors `activate_device`.)
        try:
            with transaction.atomic():
                customer.save()
        except IntegrityError:
            existing = CustomerOrg.objects.filter(
                created_by_actor_id=staff.actor_id,
                idempotency_key=idempotency_key,
            ).first()
            if existing is not None:
                return CreateCustomerResult(customer=existing, created=False)
            raise _validation_error()
        record_audit_event(
            staff,
            action="customer.created",
            target_type="customer_org",
            target_id=str(customer.id),
            request_id=idempotency_key,
            after={
                "name": customer.name,
                "status": customer.status,
                "primary_contact_email": customer.primary_contact_email,
                "country": customer.country,
                "timezone": customer.timezone,
                "plan": customer.plan,
                "seat_limit": customer.seat_limit,
            },
        )
        return CreateCustomerResult(customer=customer, created=True)


def search_customers(
    actor: ActorContext | None,
    *,
    search: str | None = None,
    first: int = 50,
) -> list[CustomerOrg]:
    require_staff_permission(actor, StaffPermission.VIEW_CUSTOMERS)
    page_size = max(1, min(first, 200))
    queryset = CustomerOrg.objects.order_by("name", "id")
    cleaned = (search or "").strip()
    if cleaned:
        queryset = queryset.filter(
            Q(name__icontains=cleaned)
            | Q(slug__icontains=cleaned)
            | Q(primary_contact_email__icontains=cleaned)
        )
    return list(queryset[:page_size])


def _customer_search_queryset(search: str | None):
    queryset = CustomerOrg.objects.all()
    cleaned = (search or "").strip()
    if cleaned:
        queryset = queryset.filter(
            Q(name__icontains=cleaned)
            | Q(slug__icontains=cleaned)
            | Q(primary_contact_email__icontains=cleaned)
        )
    return queryset


def count_customers(actor: ActorContext | None, *, search: str | None = None) -> int:
    """True match count for a customer search, independent of the page limit — so a paginating
    client sees the real total (not the page size)."""
    require_staff_permission(actor, StaffPermission.VIEW_CUSTOMERS)
    return _customer_search_queryset(search).count()


# ---------------------------------------------------------------------------
# Traditional email/password customer authentication (DEC-007 / ADR-0023).
#
# Every credential is stored as an at-rest hash + an HMAC-SHA256(SECRET_KEY) fingerprint.
# WHICH hash depends on the entropy of what is being stored, and that is the whole rule:
#   - Passwords are LOW-entropy → make_password / check_password (PBKDF2), unconditionally.
#   - Session tokens likewise keep make_password (ADR-0023; not in DEC-013's scope).
#   - Email-verify / reset tokens are HIGH-entropy (secrets.token_urlsafe(32) = 256 bits) →
#     a keyed HMAC under a distinct label (`_credential_token_hash`, DEC-013). Stretching a
#     256-bit CSPRNG secret compensates for a deficit that does not exist, and a PBKDF2
#     column is offline-testable from a DB leak in a way a keyed one is not.
# High-entropy tokens are resolved by fingerprint and confirmed with hmac.compare_digest (the
# authenticate_device_token latency optimisation).
#
# THE NO-ORACLE DISCIPLINE IS NOT UNIFORM ACROSS THESE PATHS. Do not read the rule above as a
# guarantee that none of them leaks existence. `_pad_to_floor` equalises exactly ONE endpoint,
# `resend_email_verification`. `request_password_reset` is unpadded and unauthenticated, and
# since no branch there runs a dummy PBKDF2 any more, nothing equalises its branches at all —
# the measured residual is ~2x remote. The numbers and the reasoning are in that function's own
# comment. Padding it is a separate, deliberately deferred decision — but as of 86akcmfd4 it is
# no longer UNTHROTTLED: both `request_password_reset` and `confirm_password_reset` now spend a
# per-client-IP budget before any existence-dependent branch runs, which bounds how many timing
# samples one source can take even though the gap itself is untouched.
# ---------------------------------------------------------------------------

# Config (overridable via settings; documented in deployments.md). Read at import.
ACCOUNT_SESSION_TTL = timedelta(seconds=getattr(settings, "ACCOUNT_SESSION_TTL_SECONDS", 30 * 24 * 3600))
EMAIL_VERIFY_TTL = timedelta(seconds=getattr(settings, "ACCOUNT_EMAIL_VERIFY_TTL_SECONDS", 24 * 3600))
PASSWORD_RESET_TTL = timedelta(seconds=getattr(settings, "ACCOUNT_PASSWORD_RESET_TTL_SECONDS", 3600))
LOGIN_LOCKOUT_THRESHOLD = getattr(settings, "ACCOUNT_LOGIN_LOCKOUT_THRESHOLD", 5)
LOGIN_LOCKOUT_TTL = timedelta(seconds=getattr(settings, "ACCOUNT_LOGIN_LOCKOUT_SECONDS", 900))
MIN_PASSWORD_LENGTH = getattr(settings, "ACCOUNT_MIN_PASSWORD_LENGTH", 10)
MAX_PASSWORD_LENGTH = 200

SELF_SIGNUP_ACTOR = "self_signup"
ACCOUNT_AUDIT_SURFACE = "account_graphql"

# Constant-time floor for resend-verification. The endpoint is unauthenticated and does
# WILDLY different work per branch — minting a token runs PBKDF2 and then publishes to the
# broker, while an unknown address does one indexed SELECT — so an identical response body
# still leaks existence through latency alone. Padding every call to a fixed duration makes
# the response time independent of the branch, which also keeps it true for work added later;
# equalising each operation individually does not survive maintenance.
#
# IT IS A FLOOR, NOT A CEILING. It equalises only while EVERY branch finishes inside it. Once
# a branch runs long the pad is skipped for that branch alone and the spread is simply the
# overrun — the oracle re-opens. So the number has to stay above the SLOWEST branch, and
# `_pad_to_floor` reports it when it does not (an earlier value claimed "~2x the measured
# worst case", which was never true).
#
# MEASURED, not assumed: the eligible branch's own unpadded work is ~197ms on the reference
# machine (PBKDF2 + the token INSERT + the audit row), pinned by
# `test_the_eligible_branch_costs_well_under_the_constant_time_floor`. 0.25s left ~53ms for
# dispatch, which a broker publish can exceed and an inline SMTP send always does; 0.4s keeps
# a third of the floor spare. Raising it further is cheap in throughput terms because the
# three budgets below cap how often this endpoint is reachable at all, but it is not free:
# every padded call parks a request thread, so the floor is also the lever that decides how
# much thread time a flood at the global budget can tie up.
#
# Unlike the TTLs above this is read per CALL, not at import: it is an operational knob (and
# tests switch it off), and a floor that could only change on a restart would be the kind
# that quietly stays wrong.
RESEND_MIN_SECONDS_DEFAULT = 0.4

# One overrun report per minute, not one per request — a floor that is outgrown is outgrown
# for every call, and logging each one is the unbounded logging the repo forbids (the same
# shape as the throttle store's fail-open report). State is a single module-level float, so
# it is bounded in memory too; a benign race between threads costs at most one extra line.
_FLOOR_OVERRUN_LOG_INTERVAL_SECONDS = 60.0
_last_floor_overrun_log = float("-inf")

# Budget identity used when the transport could not supply a caller address at all. A single
# shared bucket, deliberately: losing the per-IP budget must cost something visible rather
# than silently removing a limit from an unauthenticated mail-sending endpoint.
UNRESOLVED_CLIENT_IP = "unresolved-client-ip"
_UNRESOLVED_IP_LOG_INTERVAL_SECONDS = 60.0
_last_unresolved_ip_log = float("-inf")


def _reset_floor_overrun_reporting() -> None:
    """Test seam: forget the last report so a test can observe the first one deterministically
    without waiting out the suppression interval."""
    global _last_floor_overrun_log, _last_unresolved_ip_log
    _last_floor_overrun_log = float("-inf")
    _last_unresolved_ip_log = float("-inf")


def _report_unresolved_client_ip(source: str) -> None:
    """Warn — at most once per interval — that a per-IP throttle lost its key.

    `source` names which caller saw it (`resend_email_verification`, `request_password_reset`,
    `confirm_password_reset`) so the one report that survives suppression is still actionable.
    The suppression window is SHARED across all of them on purpose: the only way this fires at
    all is the GraphQL context losing its request object, which is a transport-level defect
    that would hit every unauthenticated mutation on the same surface at once — three warnings
    for one root cause would be exactly the log spam this suppression exists to prevent.
    """
    global _last_unresolved_ip_log
    now = time.monotonic()
    if now - _last_unresolved_ip_log < _UNRESOLVED_IP_LOG_INTERVAL_SECONDS:
        return
    _last_unresolved_ip_log = now
    logger.warning(
        "%s could not resolve a caller IP; spending the shared '%s' budget instead. "
        "`client_ip()` never returns empty, so this means the transport supplied no request "
        "object — most likely the GraphQL context shape changed. Every caller now shares one "
        "per-IP budget until it is fixed. Further reports suppressed for %.0fs.",
        source,
        UNRESOLVED_CLIENT_IP,
        _UNRESOLVED_IP_LOG_INTERVAL_SECONDS,
    )

# Per-address / per-IP / global budgets for resend-verification (limit, window_seconds).
# Defaults only — `enforce_budget` reads the matching setting at call time.
RESEND_ADDRESS_BUDGET = (3, 900)
RESEND_IP_BUDGET = (10, 3600)
RESEND_GLOBAL_BUDGET = (500, 3600)

# Per-client-IP budgets for the two password-reset mutations (86akcmfd4 — DEC-013's required
# follow-up: see the module-level comment above and each function's own docstring). Defaults
# only — `enforce_budget` reads the matching setting at call time.
RESET_REQUEST_IP_BUDGET = (20, 3600)
RESET_CONFIRM_IP_BUDGET = (20, 3600)

# The audit action written for a `confirm_password_reset` that got past the budget and failed
# (86ak5r2pt). See `_record_failed_reset_confirm` for what the row holds and, as much to the
# point, what it must never hold.
RESET_CONFIRM_FAILED_ACTION = "customer_user.password_reset_confirm_failed"

# Bounds on how many of those rows are written. The per-source budget bounds one source; it does
# not bound a flood from many sources (a trusted-proxy hop count set too high lets a caller pick
# its own left-hand X-Forwarded-For entry per request, i.e. a fresh source per request) and it
# bounds nothing at all while the store is down and every budget fails open. All of these skip
# the ROW and never the response, and all are sized generously: a legitimate failed confirm must
# not lose its trace, so they are flood brakes and not budgets. Settings of the same names ship
# in settings.py.
#
# TWO allowances, because one shared counter would let anyone blind the trace to the outcomes it
# exists for (see `_trace_skip_reason`):
#   - outcomes that name NO account (unknown or malformed token, an internal error before any
#     account was identified) spend a SHARED budget per hour, and a per-worker ceiling in an
#     outage;
#   - outcomes that name an ACCOUNT (consumed, expired, wrong purpose, rejected password, an
#     internal error after the token validated) spend only that account's own allowance, keyed by
#     user id: 60 an hour (a person retrying a weak password needs a handful, and the per-source
#     budget already caps one source at 20), and 30 an hour per worker in an outage, tracked in a
#     table of at most RESET_CONFIRM_TRACE_ACCOUNT_TABLE_MAX accounts.
RESET_CONFIRM_TRACE_SCOPE = "password_reset_confirm_trace_global"
RESET_CONFIRM_TRACE_BUDGET = (1000, 3600)
RESET_CONFIRM_TRACE_DEGRADED_CEILING = (200, 3600)
RESET_CONFIRM_TRACE_ACCOUNT_SCOPE = "password_reset_confirm_trace_account"
RESET_CONFIRM_TRACE_ACCOUNT_BUDGET = (60, 3600)
RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING = (30, 3600)
RESET_CONFIRM_TRACE_ACCOUNT_TABLE_MAX = 1024


class ResetConfirmOutcome(str, Enum):
    """WHY a confirm failed, for the audit row only. This is a closed set the service picks
    beside each raise; it is never an attribute of the exception and never part of a response,
    which is what keeps the five token-failure classes mutually indistinguishable to the caller
    (FR-529) while still being told apart in the trace."""

    MALFORMED_TOKEN = "malformed_token"
    UNKNOWN_TOKEN = "unknown_token"
    WRONG_PURPOSE = "wrong_purpose"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    PASSWORD_REJECTED = "password_rejected"
    # A failure whose raise site did not name its class. Recorded anyway: a missing label must
    # never become a missing row.
    UNCLASSIFIED = "unclassified"
    # The confirm failed with something that is not a coded refusal (a database error, a hasher
    # error...). The caller sees the same masked answer as for a dead token; the trace says what
    # it was.
    INTERNAL_ERROR = "internal_error"

# Per-target-email and global budgets for `request_password_reset` (86akcn8p4). Mirrors
# RESEND_ADDRESS_BUDGET / RESEND_GLOBAL_BUDGET exactly — see the setting-level comment in
# settings.py for why this closes the mail-bombing gap the per-IP budget above does not.
RESET_REQUEST_ADDRESS_BUDGET = (3, 900)
RESET_REQUEST_GLOBAL_BUDGET = (500, 3600)

# Per-client-IP budget for `verify_email` (86akcn92k). See the setting-level comment in
# settings.py: this bounds flood cost against an unauthenticated endpoint, not a guessing
# attack — the token's 256 bits of entropy already make guessing impractical.
VERIFY_EMAIL_IP_BUDGET = (20, 3600)

# --- sending while the limiter is down ---------------------------------------------------
# All three budgets above FAIL OPEN. That is right for the RESPONSE — refusing because the
# limiter is unreachable would turn an outage into a second outage, and a refusal is
# structurally distinct from `accepted:true`, so failing closed here would hand back exactly
# the enumeration oracle this endpoint is built to deny. It is wrong for the SEND: while the
# store is down, "inside your budget" and "we could not check" are the same answer, so an
# unauthenticated mail-sending endpoint would have NO ceiling at all for as long as Redis is
# out. That is mailbox flooding and unmetered provider spend, i.e. both of the things the
# three budgets exist to stop, available to anyone who notices the outage.
#
# So the response is unchanged and the SEND degrades instead, under this process-local
# ceiling. A caller whose send is skipped is left strictly no worse off than before it asked:
# the mint is skipped with it, so an existing link is neither superseded nor replaced.
#
# The ceiling is charged to EVERY call during an outage, not only to the ones that would send.
# Charging only senders would ration mail more efficiently and would also turn the ceiling
# into an account-existence oracle: it is shared, an attacker can watch it drain through their
# own inbox, and a unit that is spent only for real accounts reports exactly the thing this
# endpoint refuses to report. The three budgets above are unconditional for that same reason.
#
# PROCESS-LOCAL is the design and the limitation, in one. The shared store is precisely what
# is broken, so the fallback cannot use it; with N web workers the effective ceiling is N x
# the limit. It is a bound on catastrophe during an outage, not a budget — hence a default
# well under the (500, 3600) global one it stands in for.
#
# Memory is three scalars PER CEILING INSTANCE below, deliberately NOT a per-address or
# per-IP map: a map here would be keyed by attacker-chosen values on an unauthenticated
# endpoint, which is the unbounded growth the repo forbids, and it would grow fastest exactly
# during the flood.
RESEND_DEGRADED_SEND_CEILING = (20, 3600)
_DEGRADED_SEND_LOG_INTERVAL_SECONDS = 60.0

# 86akcn92k (F1): the reset send path gets its OWN ceiling of the same shape, extracted into
# this class so the mechanism (fixed window, lock, suppressed-interval log) is defined once
# and instantiated per caller — never a SHARED counter between resend and reset. A shared
# counter would let one endpoint's flood starve the other's legitimate degraded-mode budget,
# which is exactly the kind of cross-talk a "process-local fallback" must not have.
RESET_SEND_DEGRADED_CEILING = (20, 3600)


class _DegradedSendCeiling:
    """A process-local, per-worker fixed-window ceiling standing in for the shared throttle
    store while it is unreachable (see the module-level comment above this class for the full
    "why a send ceiling, and why unconditional" reasoning — every instance shares that
    reasoning, only the label, setting name and default differ).

    A lock, where the log suppressors elsewhere in this file accept a benign race: those cost
    at most a spare log line, this is a CEILING, and the flood it bounds is concurrent by
    definition, so an unsynchronised read-modify-write would let it be overspent by however
    many workers raced.
    """

    def __init__(self, *, label: str, setting_name: str, default: tuple[int, int]):
        self._label = label
        self._setting_name = setting_name
        self._default = default
        self._lock = threading.Lock()
        self._window_started = float("-inf")
        self._window_sends = 0
        self._last_log = float("-inf")

    def _ceiling(self) -> tuple[int, float]:
        """(limit, window_seconds) for this ceiling, read per call like the resend floor."""
        limit, window = getattr(settings, self._setting_name, self._default)
        return int(limit), float(window)

    def reset(self) -> None:
        """Test seam: forget the current window and the last report, so a test can observe the
        first skip and the first warning deterministically without waiting out either
        interval."""
        with self._lock:
            self._window_started = float("-inf")
            self._window_sends = 0
        self._last_log = float("-inf")

    def claim(self) -> bool:
        """Claim one unit of the ceiling. False means: do not send, and do not mint.

        A fixed window on `time.monotonic()` — the same shape as the store-backed limiter, so
        the degraded path is not a second rate limiter with its own semantics to reason about.

        Charged on EVERY call during an outage, including calls that could never send.
        Charging only senders would be cheaper and is wrong: the ceiling is shared, and an
        attacker can watch it drain through their own inbox, so a ceiling that only bit for
        real accounts would leak whether an address has something pending — one probe, one
        bit. That is the defect this file's docstrings already rule out for the real budgets,
        and this stands in for them.
        """
        limit, window = self._ceiling()
        now = time.monotonic()
        with self._lock:
            if now - self._window_started >= window:
                self._window_started = now
                self._window_sends = 0
            if self._window_sends >= limit:
                return False
            self._window_sends += 1
            return True

    def report_skipped(self) -> None:
        """Warn — at most once per interval — that mail is being dropped, and why.

        Rate limited for the same reason every other report on this path is: one line per
        dropped send at flood rate is the unbounded logging the repo forbids. The throttle
        store logs its own fail-open; this line carries the part that one cannot know, which
        is that the fail-open has started COSTING something.
        """
        now = time.monotonic()
        if now - self._last_log < _DEGRADED_SEND_LOG_INTERVAL_SECONDS:
            return
        self._last_log = now
        limit, window = self._ceiling()
        logger.warning(
            "%s skipped a send: limiter unavailable, so its budgets failed open and the "
            "process-local fallback ceiling (%d per %.0fs, PER WORKER) is spent. Callers "
            "still receive the normal accepted:true — the response must not reveal the "
            "outage — and no link was superseded, so an existing one still works. The remedy "
            "is to restore the rate-limit store; raising %s only buys more unmetered mail "
            "while it is down. Further reports suppressed for %.0fs.",
            self._label,
            limit,
            window,
            self._setting_name,
            _DEGRADED_SEND_LOG_INTERVAL_SECONDS,
        )


_resend_degraded_ceiling = _DegradedSendCeiling(
    label="resend-verification",
    setting_name="SELAHCUE_RESEND_DEGRADED_SEND_CEILING",
    default=RESEND_DEGRADED_SEND_CEILING,
)
_reset_send_degraded_ceiling = _DegradedSendCeiling(
    label="password-reset",
    setting_name="SELAHCUE_RESET_SEND_DEGRADED_CEILING",
    default=RESET_SEND_DEGRADED_CEILING,
)


# --- thin free-function wrappers over `_resend_degraded_ceiling`, kept for the exact names
# and signatures `resend_email_verification` and its tests already call. ------------------
def _degraded_send_ceiling() -> tuple[int, float]:
    return _resend_degraded_ceiling._ceiling()


def _reset_degraded_send_window() -> None:
    _resend_degraded_ceiling.reset()


def _claim_degraded_send() -> bool:
    return _resend_degraded_ceiling.claim()


def _report_degraded_send_skipped() -> None:
    _resend_degraded_ceiling.report_skipped()


# --- the reset-send sibling (86akcn92k, F1) -------------------------------------------------
def _reset_reset_send_degraded_window() -> None:
    """Test seam, same purpose as `_reset_degraded_send_window` above but for the reset send's
    own ceiling."""
    _reset_send_degraded_ceiling.reset()


def _claim_degraded_reset_send() -> bool:
    """`_claim_degraded_send`'s sibling for `request_password_reset`. See
    `_DegradedSendCeiling.claim` and the module-level "sending while the limiter is down"
    comment for the shared reasoning; this claims from the RESET ceiling, never the resend
    one, so one endpoint's outage-time flood cannot spend the other's degraded budget."""
    return _reset_send_degraded_ceiling.claim()


def _report_reset_degraded_send_skipped() -> None:
    """`_report_degraded_send_skipped`'s sibling for the reset send path."""
    _reset_send_degraded_ceiling.report_skipped()


# A fixed hash to run check_password against on unknown-email login, so the unknown-email and
# wrong-password paths take the same PBKDF2 time (no timing oracle on account existence).
_DUMMY_PASSWORD_HASH = make_password("selahcue-timing-equalizer-not-a-real-password")


# --- injectable email delivery seam ---------------------------------------
class EmailSender:
    """Delivery seam for account emails. The default is a no-op (no SMTP creds yet, DEC-007);
    a concrete provider is wired later behind this same interface. Tests override it to capture
    the show-once raw token that a real email would carry."""

    def send_email_verification(self, user: CustomerUser, raw_token: str) -> None:  # pragma: no cover
        pass

    def send_password_reset(self, user: CustomerUser, raw_token: str) -> None:  # pragma: no cover
        pass

    def send_account_exists(self, email: str) -> None:  # pragma: no cover
        # Sent when a signup targets an already-registered email — so the real owner is notified
        # without revealing account existence to the (uniform accepted:true) caller.
        pass


_email_sender: EmailSender = EmailSender()


def get_email_sender() -> EmailSender:
    return _email_sender


def set_email_sender(sender: EmailSender) -> None:
    """Override the delivery seam (tests / provider wiring)."""
    global _email_sender
    _email_sender = sender


# --- credential helpers ----------------------------------------------------
def _fingerprint(value: str) -> str:
    # Same HMAC pepper (SECRET_KEY) as the device/license slices.
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _credential_token_hash(value: str) -> str:
    """At-rest hash for a CredentialToken (DEC-013 / ADR-0023).

    NOT `make_password`. Key stretching buys exactly one thing — time against guessing a
    LOW-entropy secret — and there is no such deficit here: `_generate_token` is
    `secrets.token_urlsafe(32)`, 256 bits of CSPRNG output, so a PBKDF2 column costs ~110ms
    per mint to slow an attacker who was never going to finish the first place.

    It also costs security, which is the part that decided this. A PBKDF2 column stores its
    salt beside the hash and is therefore offline-testable from a DB leak alone; a keyed HMAC
    is not testable at all without SECRET_KEY, which a DB leak does not contain. Same pepper
    as `_fingerprint`, under a DISTINCT LABEL so the two columns are not the same value —
    `token_fingerprint` resolves the row and this confirms it, and a column that merely
    repeated the lookup key would confirm nothing.

    The column stays (no migration, and ADR-0023's `DeviceToken` clone keeps its shape); only
    what goes in it changes. It is write-only for CredentialToken — verification is by
    fingerprint plus `hmac.compare_digest` — so nothing reads this back with `check_password`.
    """
    return _fingerprint(f"credential-token-hash:{value}")


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _require_valid_email(raw: str) -> str:
    email = _normalize_email(raw)
    try:
        validate_email(email)
    except ValidationError as error:
        raise _validation_error() from error
    return email


def _email_fingerprint(email: str) -> str:
    return _fingerprint(email)


def _validate_password(password: str, *, code: ErrorCode = ErrorCode.VALIDATION_FAILED) -> None:
    """Length policy only (v1); complexity/breach checks are a later slice.

    `code` selects which coded failure a rejection raises, and the choice is a security
    boundary, not a style preference. The default is the collapsed VALIDATION_FAILED, so a
    caller who has proved nothing (signup) learns nothing. `confirm_password_reset` passes
    PASSWORD_INVALID — but only from BEHIND a validated token, never before one. Defaulting
    to the collapsed code is what makes a future third caller fail SAFE.
    """
    # Do NOT strip — spaces can be intentional — but reject an all-whitespace password.
    if not isinstance(password, str) or not password.strip():
        raise SafeAPIError(code)
    # A string that cannot be encoded as UTF-8 (lone surrogates, which JSON "\ud800" escapes
    # produce) passes the length rule and then makes the hasher raise UnicodeEncodeError. In
    # `confirm_password_reset` that happens after the token has been marked consumed, inside
    # the transaction, so it was an unexpected failure rather than a refused password.
    try:
        password.encode("utf-8")
    except UnicodeEncodeError:
        raise SafeAPIError(code) from None
    if not (MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH):
        raise SafeAPIError(code)


def _generate_token(label: str) -> str:
    # High-entropy, URL-safe (usable directly in an email link).
    return f"SC-{label}-{secrets.token_urlsafe(32)}"


def _mask(full_token: str) -> tuple[str, str, str]:
    prefix = full_token[:12]
    suffix = full_token[-4:]
    return prefix, suffix, f"{prefix}...{suffix}"


def _mint_credential_token(user: CustomerUser, purpose: str, ttl: timedelta) -> str:
    """Create a single-use CredentialToken and return its raw (show-once) value."""
    raw = _generate_token("EVF" if purpose == CredentialTokenPurpose.EMAIL_VERIFY else "PRS")
    _prefix, _suffix, masked = _mask(raw)
    token = CredentialToken(
        customer_user=user,
        purpose=purpose,
        token_hash=_credential_token_hash(raw),
        token_fingerprint=_fingerprint(raw),
        masked_token=masked,
        expires_at=djtz.now() + ttl,
    )
    try:
        token.full_clean()
    except ValidationError as error:
        raise _validation_error() from error
    token.save()
    return raw


def _new_session(user: CustomerUser, now) -> tuple[CustomerSession, str]:
    """Mint an ACTIVE opaque session token (show-once). Returns (session, raw_token)."""
    raw = _generate_token("ACS")
    prefix, suffix, masked = _mask(raw)
    session = CustomerSession(
        customer_user=user,
        token_prefix=prefix,
        token_suffix=suffix,
        masked_token=masked,
        token_hash=make_password(raw),
        token_fingerprint=_fingerprint(raw),
        status=CustomerSessionStatus.ACTIVE,
        issued_at=now,
        expires_at=now + ACCOUNT_SESSION_TTL,
    )
    try:
        session.full_clean()
    except ValidationError as error:
        raise _validation_error() from error
    session.save()
    return session, raw


def _customer_actor(user: CustomerUser) -> ActorContext:
    return ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id=str(user.id),
        org_id=str(user.customer_id),
        role=user.role,
    )


# --- result dataclasses ----------------------------------------------------
@dataclass(frozen=True)
class RegisterCustomerUserData:
    idempotency_key: str
    email: str
    password: str
    org_name: str
    country: str
    display_name: str = ""
    timezone: str = "UTC"


@dataclass(frozen=True)
class AcceptedResult:
    # Uniform result for no-enumeration endpoints (signup, password-reset request).
    accepted: bool


@dataclass(frozen=True)
class VerifyEmailResult:
    verified: bool


@dataclass(frozen=True)
class LoginResult:
    session_token: str  # show-once opaque token
    expires_at: str
    role: str
    org_id: str


@dataclass(frozen=True)
class RefreshResult:
    session_token: str  # new (rotated) show-once token
    expires_at: str


@dataclass(frozen=True)
class LogoutResult:
    revoked: bool


@dataclass(frozen=True)
class ConfirmPasswordResetResult:
    reset: bool


# --- services --------------------------------------------------------------
def register_customer_user(data: RegisterCustomerUserData) -> AcceptedResult:
    """Self-serve signup (DEC-007 product answer): create a NEW CustomerOrg (TRIAL) and its first
    Admin user atomically, then email a verification token. Returns a UNIFORM accepted:true whether
    or not the email already exists — no user-enumeration oracle."""
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    email = _require_valid_email(data.email)
    _validate_password(data.password)
    org_name = " ".join(data.org_name.strip().split())
    country = data.country.strip().upper()
    if not org_name or len(country) != 2:
        raise _validation_error()
    fingerprint = _email_fingerprint(email)
    # Namespace the (actor, idempotency_key) guard PER EMAIL: two distinct signups that happen to
    # pick the same client idempotency key must not alias and swallow one another. Email is the real
    # identity for self-signup, so the email fingerprint is the correct namespace.
    self_actor = f"{SELF_SIGNUP_ACTOR}:{fingerprint}"
    password_hash = make_password(data.password)

    with transaction.atomic():
        # Idempotency AND no-enumeration in one check: any prior account for this email (a retry OR
        # an already-registered address) returns the uniform accepted:true without a duplicate.
        if CustomerUser.objects.filter(email_fingerprint=fingerprint).exists():
            # on_commit, not inline: the sender now publishes to Redis for a worker to pick up.
            # Dispatching inside the transaction would queue a real email that a rollback then
            # un-does, and the recipient would act on a message about state that never existed.
            transaction.on_commit(lambda: get_email_sender().send_account_exists(email))
            return AcceptedResult(accepted=True)

        # Create the org + first Admin under a SINGLE savepoint, so a failure on EITHER rolls BOTH
        # back — never an orphan org. Retry ONLY a slug collision (fresh slug); a lost email race
        # converges on the uniform accepted:true.
        user = None
        for _attempt in range(4):
            org = CustomerOrg(
                name=org_name,
                slug=_unique_slug(org_name),
                status=CustomerStatus.TRIAL,
                primary_contact_email=email,
                country=country,
                timezone=data.timezone.strip() or "UTC",
                plan="TRIAL",
                seat_limit=1,
                created_by_actor_id=self_actor,
                idempotency_key=idempotency_key,
            )
            candidate = CustomerUser(
                customer=org,
                email=email,
                email_fingerprint=fingerprint,
                password_hash=password_hash,
                status=CustomerUserStatus.INVITED,
                role=CustomerRole.ADMIN,  # first (and only) user in a self-serve org is the Admin
                display_name=" ".join(data.display_name.strip().split()),
                created_by_actor_id=self_actor,
                idempotency_key=idempotency_key,
            )
            # Field-format validation only; DB unique constraints (+ the IntegrityError branch) decide
            # collisions, so a racing duplicate never leaks a VALIDATION_FAILED.
            try:
                org.full_clean(validate_unique=False)
                candidate.full_clean(exclude=["customer"], validate_unique=False)
            except ValidationError as error:
                raise _validation_error() from error
            try:
                with transaction.atomic():
                    org.save()
                    candidate.customer = org  # re-bind so customer_id picks up the saved org pk
                    candidate.save()
            except IntegrityError:
                # A concurrent signer won the unique email (or this email's (actor, key)) → idempotent.
                if CustomerUser.objects.filter(email_fingerprint=fingerprint).exists():
                    return AcceptedResult(accepted=True)
                # Otherwise it was a slug collision — recompute a fresh slug and retry.
                continue
            user = candidate
            break
        if user is None:
            # Persistent non-email collision (astronomically unlikely) — fail closed, create nothing.
            raise _validation_error()

        raw_token = _mint_credential_token(user, CredentialTokenPurpose.EMAIL_VERIFY, EMAIL_VERIFY_TTL)
        record_audit_event(
            _customer_actor(user),
            action="customer_user.registered",
            target_type="customer_user",
            target_id=str(user.id),
            request_id=idempotency_key,
            source_surface=ACCOUNT_AUDIT_SURFACE,
            after={"org_id": str(org.id), "role": user.role, "status": user.status},
        )
        # on_commit: a rollback after this point would otherwise leave a verification email
        # queued carrying a token whose CredentialToken row no longer exists — the recipient
        # gets a link that fails validation with no way to tell why.
        verified_user, verify_token = user, raw_token
        transaction.on_commit(
            lambda: get_email_sender().send_email_verification(verified_user, verify_token)
        )
        return AcceptedResult(accepted=True)


def verify_email(raw_token: str, client_ip: str = "") -> VerifyEmailResult:
    """Consume an EMAIL_VERIFY token: mark the user ACTIVE + email_verified_at. Every failure
    (unknown / wrong-purpose / consumed / expired) collapses to VALIDATION_FAILED (no oracle).

    Spends a per-client-IP budget FIRST, before the token is even looked at (86akcn92k) —
    the same placement as `confirm_password_reset`'s own budget, and for the same reason:
    `RATE_LIMITED` must fire identically whether the offered token was live, dead, or never
    existed, so it cannot become a sixth, more-informative token-failure code alongside the
    existing collapsed `VALIDATION_FAILED`.

    LOWER severity than the reset paths, on purpose — see the setting's own comment in
    settings.py. `client_ip` defaults to `""` (unresolved) rather than being required, so
    existing direct-service-call test fixtures that mint-and-verify a user without going
    through the GraphQL transport keep working unchanged; `""` still spends a budget (the
    shared `UNRESOLVED_CLIENT_IP` bucket), it just does not distinguish callers.
    """
    if not client_ip:
        _report_unresolved_client_ip("verify_email")
    enforce_budget(
        "verify_email_ip",
        client_ip or UNRESOLVED_CLIENT_IP,
        "SELAHCUE_THROTTLE_VERIFY_EMAIL_IP",
        VERIFY_EMAIL_IP_BUDGET,
    )
    token_value = (raw_token or "").strip()
    if not token_value:
        raise _validation_error()
    fingerprint = _fingerprint(token_value)
    now = djtz.now()
    with transaction.atomic():
        try:
            token = (
                CredentialToken.objects.select_for_update()
                .select_related("customer_user")
                .get(token_fingerprint=fingerprint)
            )
        except CredentialToken.DoesNotExist as error:
            raise _validation_error() from error
        if not hmac.compare_digest(token.token_fingerprint, fingerprint):
            raise _validation_error()
        if (
            token.purpose != CredentialTokenPurpose.EMAIL_VERIFY
            or token.consumed_at is not None
            or token.expires_at <= now
        ):
            raise _validation_error()
        token.consumed_at = now
        token.save(update_fields=["consumed_at"])
        user = token.customer_user
        user.email_verified_at = now
        user.status = CustomerUserStatus.ACTIVE
        user.save(update_fields=["email_verified_at", "status", "updated_at"])
        record_audit_event(
            _customer_actor(user),
            action="customer_user.email_verified",
            target_type="customer_user",
            target_id=str(user.id),
            request_id=token.masked_token,
            source_surface=ACCOUNT_AUDIT_SURFACE,
            after={"status": user.status},
        )
    return VerifyEmailResult(verified=True)


@dataclass(frozen=True)
class ResendVerificationData:
    email: str
    # Caller IP for the per-source budget. Resolved by the transport (`throttling.client_ip`),
    # never read from a header here — the service has no way to know which hops are trusted.
    client_ip: str = ""


def _pad_to_floor(started: float) -> None:
    """Hold the response until the floor has elapsed; report it when the floor is outgrown.

    This is the PRIMARY defence against the timing oracle: the caller observes one duration
    regardless of which branch ran, so latency carries no information about whether the
    address exists. It is deliberately a floor on the WHOLE call rather than a per-operation
    equaliser — the branches differ by a PBKDF2 hash, an INSERT, an audit row and a broker
    publish, and matching those individually would have to be re-done every time either
    branch gains work.

    NAMED A FLOOR ON PURPOSE. The previous name (`_pad_to_constant_time`) asserted a property
    this code only conditionally provides: the call is constant-time only while every branch
    fits inside the floor. A branch that overruns is not padded at all, so the observable
    spread becomes exactly its overrun and the oracle is back — silently, because a floor that
    is too small looks identical to one that is generous.

    Hence the report. It cannot fix the overrun (sleeping longer after the fact would not
    equalise anything — the branch that FITS would still return at the floor), so the only
    useful response is to make the operator aware the knob is now wrong. Rate-limited, because
    an outgrown floor is outgrown for every call.

    Cost: one request thread parked for up to the floor. That is affordable precisely because
    the three budgets above cap how often this endpoint can be reached at all.
    """
    floor = float(getattr(settings, "ACCOUNT_RESEND_MIN_SECONDS", RESEND_MIN_SECONDS_DEFAULT))
    if floor <= 0:
        return
    elapsed = time.monotonic() - started
    remaining = floor - elapsed
    if remaining > 0:
        time.sleep(remaining)
        return
    _report_floor_overrun(elapsed=elapsed, floor=floor)


def _report_floor_overrun(*, elapsed: float, floor: float) -> None:
    """Warn — at most once per interval — that a branch ran past the constant-time floor."""
    global _last_floor_overrun_log
    now = time.monotonic()
    if now - _last_floor_overrun_log < _FLOOR_OVERRUN_LOG_INTERVAL_SECONDS:
        return
    _last_floor_overrun_log = now
    # warning, not exception: no traceback, one line, and it names the remedy. The overrun
    # size is the actionable part — it is how far the oracle is open and how much the floor
    # would have to rise to close it.
    logger.warning(
        "resend-verification exceeded its constant-time floor: %.0fms elapsed against a "
        "%.0fms floor, overran by %.0fms. While a branch runs past the floor the padding "
        "equalises nothing and response time is again an account-existence oracle. Raise "
        "ACCOUNT_RESEND_MIN_SECONDS above the slowest branch, or make dispatch cheaper "
        "(CELERY_TASK_ALWAYS_EAGER puts the SMTP send inline on this path). Further reports "
        "suppressed for %.0fs.",
        elapsed * 1000,
        floor * 1000,
        (elapsed - floor) * 1000,
        _FLOOR_OVERRUN_LOG_INTERVAL_SECONDS,
    )


def resend_email_verification(data: ResendVerificationData) -> AcceptedResult:
    """Re-issue an email-verification link (DEC-007). Always returns accepted:true.

    The design constraint is that the caller learns NOTHING. Three cases — no account,
    an unverified account, an already-verified (or disabled) account — return a byte-identical
    payload AND take the same time. Only the middle case sends anything, and only its owner
    can see that it did.

    Rate limiting is spent BEFORE any of that, on three keys: the target address (mailbox
    flooding), the source IP (spraying distinct addresses), and a global ceiling (total send
    cost). The address budget is spent whether or not the account exists — a limiter that
    only bit for real accounts would itself be the oracle this function exists to avoid.

    All three FAIL OPEN when the limiter store is down, which would otherwise leave this
    endpoint's send path unbounded for the length of the outage. It does not: an outage
    degrades the SEND under `_claim_degraded_send`, never the response. See the ceiling's
    comment for why that asymmetry is the only safe one here.
    """
    started = time.monotonic()
    normalized = _require_valid_email(data.email)
    fingerprint = _email_fingerprint(normalized)

    # Widest budget first, so a global flood cannot be diagnosed by watching which specific
    # limit trips. The address key is an HMAC fingerprint: raw addresses must not land in
    # Redis keys. Rate-limited calls are NOT padded — a RATE_LIMITED response is already
    # structurally distinct from accepted:true, so its timing reveals nothing further, and
    # padding a rejection would hand an attacker a way to tie up threads.
    # `enforce_budget_reporting_outage`, not `enforce_budget`: a fail-open still permits the
    # call (see below), but the send path needs to KNOW it was a fail-open rather than a real
    # allow. `|=` and three separate statements, never `or`: short-circuiting would stop
    # spending the later budgets, and every one of them must be spent on every call.
    limiter_degraded = enforce_budget_reporting_outage(
        "resend_verify", "global", "SELAHCUE_THROTTLE_RESEND_GLOBAL", RESEND_GLOBAL_BUDGET
    )
    # The per-IP budget is ALWAYS spent. It used to be conditional (`if data.client_ip`), which
    # made it fail open: `client_ip()` itself never returns empty (it falls back to "unknown"),
    # so the only way to get here without an address is the transport failing to supply a
    # request at all — i.e. a change in Strawberry's context shape would have silently deleted
    # this budget on an unauthenticated mail-sending endpoint, with no error and no log.
    # Spending one shared bucket instead makes that loss loud: everyone lands in the same
    # 10/hour budget, so the misconfiguration shows up as refusals rather than as an
    # unmetered send path.
    if not data.client_ip:
        _report_unresolved_client_ip("resend_email_verification")
    limiter_degraded |= enforce_budget_reporting_outage(
        "resend_verify_ip",
        data.client_ip or UNRESOLVED_CLIENT_IP,
        "SELAHCUE_THROTTLE_RESEND_IP",
        RESEND_IP_BUDGET,
    )
    limiter_degraded |= enforce_budget_reporting_outage(
        "resend_verify_addr", fingerprint, "SELAHCUE_THROTTLE_RESEND_ADDRESS", RESEND_ADDRESS_BUDGET
    )
    # The fallback ceiling is spent HERE — beside the three budgets it stands in for, before
    # anything has looked the address up, and therefore whether or not the account exists.
    # That last part is the whole point: the ceiling is shared and an attacker can watch it
    # drain through their own inbox, so charging only the calls that really send would make
    # its depletion a readout of whether a probed address had a verification pending. One
    # request per target, one bit each time. The three budgets above are spent unconditionally
    # for exactly this reason and this must match them.
    #
    # It is not free: while the store is down, a flood of probes can now starve legitimate
    # resends. That is the same cost the global budget already accepts, and it is the cheaper
    # side of the trade — a delayed verification email against a working enumeration oracle.
    degraded_send_allowed = True
    if limiter_degraded:
        degraded_send_allowed = _claim_degraded_send()

    try:
        now = djtz.now()
        with transaction.atomic():
            user = CustomerUser.objects.filter(email_fingerprint=fingerprint).first()
            # Only an account that is still awaiting its FIRST verification gets a new link.
            # An already-verified account has nothing to verify, and a DISABLED one must not
            # be handed a fresh way in — a revoked seat should not be revivable by asking.
            eligible = (
                user is not None
                and user.email_verified_at is None
                and user.status == CustomerUserStatus.INVITED
            )
            if not eligible:
                # No equaliser here any more, and its removal is REQUIRED rather than tidy.
                # It existed to burn the same PBKDF2 the minting branch burned; DEC-013 took
                # PBKDF2 out of the mint, so keeping it would have inverted the very oracle it
                # was written to close — the eligible branch would finish in ~1.4ms while this
                # one burned ~450ms, and a FAST response would mean "this account exists".
                # Equalisation is the floor's job (`_pad_to_floor`), which pads every branch
                # that finishes inside it; both branches now do, by a wide margin.
                return AcceptedResult(accepted=True)

            # The limiter failed open and this call's claim on the fallback ceiling was
            # refused: skip the send. The MINT is skipped with it, on purpose — superseding a
            # live link and then not delivering its replacement would leave this caller worse
            # off than if they had never asked, trading a working link for nothing. Like the
            # branch above it carries no dummy PBKDF2: see there for why removing it was
            # required by DEC-013 rather than merely tidy.
            if not degraded_send_allowed:
                _report_degraded_send_skipped()
                return AcceptedResult(accepted=True)

            # Supersede any live link, so the previous email stops working the moment a new
            # one is issued (a stale link in an old mailbox must not remain a way in).
            CredentialToken.objects.filter(
                customer_user=user,
                purpose=CredentialTokenPurpose.EMAIL_VERIFY,
                consumed_at__isnull=True,
            ).update(consumed_at=now)
            raw_token = _mint_credential_token(user, CredentialTokenPurpose.EMAIL_VERIFY, EMAIL_VERIFY_TTL)
            record_audit_event(
                _customer_actor(user),
                action="customer_user.verification_resent",
                target_type="customer_user",
                target_id=str(user.id),
                # The token FINGERPRINT, never the token: enough to correlate the audit row
                # with the credential, useless as the credential.
                request_id=_fingerprint(raw_token),
                source_surface=ACCOUNT_AUDIT_SURFACE,
                after={},
            )
            # on_commit: same reason as signup and reset — a rolled-back resend must not
            # leave a live email pointing at a token row that was never committed.
            target_user, target_token = user, raw_token
            transaction.on_commit(
                lambda: get_email_sender().send_email_verification(target_user, target_token)
            )
        return AcceptedResult(accepted=True)
    finally:
        _pad_to_floor(started)


@dataclass(frozen=True)
class LoginData:
    email: str
    password: str


def login(data: LoginData, *, source_surface: str = ACCOUNT_AUDIT_SURFACE) -> LoginResult:
    """Authenticate email/password and mint a session. Unknown-email and wrong-password are
    indistinguishable (both UNAUTHENTICATED, equal timing). Unverified/disabled → POLICY_DENIED
    only AFTER a correct password (so state leaks only to the real owner).

    `source_surface` is only the provenance recorded on the audit row, so a session minted over
    the native `/v1/sessions` route is distinguishable from one minted on the browser surface
    (86ak5t1gw). It changes nothing about who may sign in or how."""
    email = _normalize_email(data.email)
    fingerprint = _email_fingerprint(email)
    now = djtz.now()

    # Read (no lock) and run the slow PBKDF2 outside any transaction — holding a row lock across
    # check_password would serialise all logins for a user for no benefit.
    user = CustomerUser.objects.filter(email_fingerprint=fingerprint).first()
    if user is None:
        # Equalise timing with the wrong-password path; then deny with no oracle.
        check_password(data.password, _DUMMY_PASSWORD_HASH)
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if user.locked_until is not None and user.locked_until > now:
        # Do NOT leak the locked state: a distinct RATE_LIMITED code (429) would be an existence
        # oracle, since only real accounts can be locked. Equalise timing (run the hash) and deny
        # with the SAME UNAUTHENTICATED as unknown-email / wrong-password. Lockout still blocks —
        # even a correct password is refused while locked.
        check_password(data.password, user.password_hash)
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if not check_password(data.password, user.password_hash):
        # Persist the failed attempt in its OWN committed transaction: it MUST survive the raise
        # below. A single atomic wrapping the whole login would roll the counter back on the raise,
        # so lockout would never accrue.
        with transaction.atomic():
            locked = CustomerUser.objects.select_for_update().get(pk=user.pk)
            locked.failed_login_count += 1
            if locked.failed_login_count >= LOGIN_LOCKOUT_THRESHOLD:
                locked.locked_until = now + LOGIN_LOCKOUT_TTL
                locked.failed_login_count = 0
            locked.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if user.email_verified_at is None or user.status != CustomerUserStatus.ACTIVE:
        raise SafeAPIError(ErrorCode.POLICY_DENIED)

    with transaction.atomic():
        locked = CustomerUser.objects.select_for_update().get(pk=user.pk)
        if locked.failed_login_count or locked.locked_until:
            locked.failed_login_count = 0
            locked.locked_until = None
            locked.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
        session, raw = _new_session(locked, now)
        record_audit_event(
            _customer_actor(locked),
            action="customer_user.logged_in",
            target_type="customer_session",
            target_id=str(session.id),
            request_id=session.token_fingerprint,
            source_surface=source_surface,
            after={"masked_token": session.masked_token, "expires_at": session.expires_at.isoformat()},
        )
    return LoginResult(
        session_token=raw,
        expires_at=session.expires_at.isoformat(),
        role=locked.role,
        org_id=str(locked.customer_id),
    )


def authenticate_session(presented_token: str) -> tuple[CustomerSession, CustomerUser]:
    """Resolve + validate a presented account session token. Any failure → UNAUTHENTICATED with no
    oracle. Rejects sessions issued before the user's last password change (mass invalidation)."""
    token_value = (presented_token or "").strip()
    if not token_value:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    fingerprint = _fingerprint(token_value)
    try:
        session = CustomerSession.objects.select_related("customer_user", "customer_user__customer").get(
            token_fingerprint=fingerprint
        )
    except CustomerSession.DoesNotExist as error:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED) from error
    if not hmac.compare_digest(session.token_fingerprint, fingerprint):
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if session.status != CustomerSessionStatus.ACTIVE:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if session.expires_at <= djtz.now():
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    user = session.customer_user
    if user.status != CustomerUserStatus.ACTIVE:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if user.password_changed_at is not None and session.issued_at < user.password_changed_at:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    return session, user


def actor_from_session_token(presented_token: str | None) -> ActorContext | None:
    """Non-raising resolver for graphql/context.py: presented token → CUSTOMER actor, or None."""
    if not presented_token:
        return None
    try:
        _session, user = authenticate_session(presented_token)
    except SafeAPIError:
        return None
    return _customer_actor(user)


def refresh_session(presented_token: str) -> RefreshResult:
    """Rotate the session: revoke the presented token, mint a fresh one with an extended window."""
    now = djtz.now()
    with transaction.atomic():
        session, user = authenticate_session(presented_token)
        session.status = CustomerSessionStatus.REVOKED
        session.revoked_at = now
        session.save(update_fields=["status", "revoked_at", "updated_at"])
        new_session, raw = _new_session(user, now)
        record_audit_event(
            _customer_actor(user),
            action="customer_user.session_refreshed",
            target_type="customer_session",
            target_id=str(new_session.id),
            request_id=new_session.token_fingerprint,
            source_surface=ACCOUNT_AUDIT_SURFACE,
            after={"masked_token": new_session.masked_token, "expires_at": new_session.expires_at.isoformat()},
        )
    return RefreshResult(session_token=raw, expires_at=new_session.expires_at.isoformat())


def logout_session(presented_token: str, *, all_sessions: bool = False) -> LogoutResult:
    """Revoke the presented session (or every ACTIVE session for the user). Revokes the ACCOUNT
    session ONLY — never a DeviceToken or cached entitlement (never-blank: device stays live)."""
    now = djtz.now()
    with transaction.atomic():
        session, user = authenticate_session(presented_token)
        if all_sessions:
            CustomerSession.objects.filter(
                customer_user=user, status=CustomerSessionStatus.ACTIVE
            ).update(status=CustomerSessionStatus.REVOKED, revoked_at=now, updated_at=now)
        else:
            session.status = CustomerSessionStatus.REVOKED
            session.revoked_at = now
            session.save(update_fields=["status", "revoked_at", "updated_at"])
        record_audit_event(
            _customer_actor(user),
            action="customer_user.logged_out",
            target_type="customer_user",
            target_id=str(user.id),
            request_id=session.token_fingerprint,
            source_surface=ACCOUNT_AUDIT_SURFACE,
            after={"all_sessions": all_sessions},
        )
    return LogoutResult(revoked=True)


def request_password_reset(email: str, client_ip: str = "") -> AcceptedResult:
    """Always returns accepted:true (no enumeration). When the email matches a user, invalidate any
    prior unconsumed reset tokens and email a fresh single-use one.

    Spends THREE budgets before any existence-dependent branch runs — global, then per-client-IP,
    then per-target-email — mirroring `resend_email_verification`'s shape exactly (86akcn8p4,
    Sana's more-urgent follow-up to 86akcmfd4). The per-IP budget alone (86akcmfd4, DEC-013's
    required follow-up) bounds how many timing samples one source can take against the mint-vs-
    no-mint branch (see the `else` branch below for why it does not close that gap); it does
    nothing to bound MAIL VOLUME against one victim, which is a different threat with a different
    key. A distributed attacker sprays distinct source IPs — cheap even before IPv6 (86akcn8ww)
    makes it nearly free — so the address budget is what actually caps how many reset emails one
    mailbox can receive, and the global budget caps total send cost the same way
    `RESEND_GLOBAL_BUDGET` does.

    Widest first (global), exactly as resend does it, so a global flood cannot be diagnosed by
    watching which specific limit tripped. Every budget is spent UNCONDITIONALLY, before the
    existence check: a limiter that only bit for real accounts would itself be an existence
    oracle, and the per-address key is `_email_fingerprint` — the same HMAC the mint branch below
    already computes — never the raw submitted email, for the same cache-key-cardinality reason
    resend already solved. `RATE_LIMITED` cannot leak anything about the email either way — it is
    decided purely by request COUNT, before any existence-dependent branch runs, so a throttled
    caller learns nothing about the email they sent. Not padded when rate-limited, same as resend:
    `RATE_LIMITED` is already structurally distinct from `accepted:true`, so its timing reveals
    nothing further, and padding a rejection would hand an attacker a way to tie up threads.

    All three budgets FAIL OPEN while the store is down (86akcn92k, F1) — correct for the
    RESPONSE, for the same reason resend's docstring gives, but wrong for the SEND: without a
    stand-in, an outage would revert this endpoint to unmetered mail and unbounded oracle
    sampling, i.e. exactly the pre-86akcmfd4 state. So the send (never the response) degrades
    under `_claim_degraded_reset_send` — this endpoint's OWN ceiling, never shared with
    resend's — mirroring `resend_email_verification`'s `enforce_budget_reporting_outage` /
    `_claim_degraded_send` shape exactly. `|=` and three separate statements, never `or`: see
    resend's own comment for why short-circuiting would stop spending the later budgets.
    """
    normalized = _require_valid_email(email)
    fingerprint = _email_fingerprint(normalized)

    limiter_degraded = enforce_budget_reporting_outage(
        "password_reset_request_global",
        "global",
        "SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL",
        RESET_REQUEST_GLOBAL_BUDGET,
    )
    if not client_ip:
        _report_unresolved_client_ip("request_password_reset")
    limiter_degraded |= enforce_budget_reporting_outage(
        "password_reset_request_ip",
        client_ip or UNRESOLVED_CLIENT_IP,
        "SELAHCUE_THROTTLE_RESET_REQUEST",
        RESET_REQUEST_IP_BUDGET,
    )
    limiter_degraded |= enforce_budget_reporting_outage(
        "password_reset_request_addr",
        fingerprint,
        "SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS",
        RESET_REQUEST_ADDRESS_BUDGET,
    )
    # Claimed HERE, before anything has looked the address up — same reasoning as resend's own
    # ceiling claim: charging only calls that would really send turns the ceiling's depletion
    # into an existence oracle (an attacker watching it drain through their own inbox).
    degraded_send_allowed = True
    if limiter_degraded:
        degraded_send_allowed = _claim_degraded_reset_send()

    now = djtz.now()
    with transaction.atomic():
        user = CustomerUser.objects.filter(email_fingerprint=fingerprint).first()
        if user is not None:
            # The limiter failed open and this call's claim on the fallback ceiling was
            # refused: skip the send. The MINT is skipped with it, on purpose — same reasoning
            # as resend's own docstring: superseding a live link and then not delivering its
            # replacement would leave this caller worse off than before they asked.
            if not degraded_send_allowed:
                _report_reset_degraded_send_skipped()
                return AcceptedResult(accepted=True)
            CredentialToken.objects.filter(
                customer_user=user,
                purpose=CredentialTokenPurpose.PASSWORD_RESET,
                consumed_at__isnull=True,
            ).update(consumed_at=now)
            raw_token = _mint_credential_token(user, CredentialTokenPurpose.PASSWORD_RESET, PASSWORD_RESET_TTL)
            record_audit_event(
                _customer_actor(user),
                action="customer_user.password_reset_requested",
                target_type="customer_user",
                target_id=str(user.id),
                request_id=_fingerprint(raw_token),
                source_surface=ACCOUNT_AUDIT_SURFACE,
                after={},
            )
            # on_commit: same reason as signup — a rolled-back reset must not leave a live
            # email pointing at a token row that was never committed.
            reset_user, reset_token = user, raw_token
            transaction.on_commit(
                lambda: get_email_sender().send_password_reset(reset_user, reset_token)
            )
        else:
            # Deliberately empty: the minting branch no longer runs a PBKDF2 (DEC-013), so a
            # dummy one here would make the NON-EXISTENT-account branch the expensive one and
            # invert the oracle.
            #
            # NO FLOOR APPLIES ON THIS PATH. `_pad_to_floor` is called only from
            # `resend_email_verification`; `request_password_reset` is still unpadded, so
            # nothing here equalises the two branches' DURATION. What used to obscure the gap
            # was the minting branch's own PBKDF2 noise, never a constant-time guarantee.
            # Measured, removing that PBKDF2 moved the branch gap from +2.66ms (sd 83ms) to
            # +0.437ms (sd 0.27ms): absolutely smaller, but far cheaper to sample now that the
            # noise hiding it shrank with it. Modelled against network jitter that is roughly a
            # 2x reduction in remote attack cost — a modest regression of a PRE-EXISTING oracle,
            # not a new one — and it collapses further for a co-located attacker. Signup is
            # unaffected: its password PBKDF2 runs before the branch.
            #
            # Padding this path (closing the gap itself) is a separate, deliberately deferred
            # decision — it is not what 86akcmfd4 does. What 86akcmfd4 DOES do is spend a
            # per-client-IP budget before this function is even entered (see the docstring),
            # which bounds how many times one source can sample this gap rather than closing it.
            pass
    return AcceptedResult(accepted=True)


@dataclass
class _ResetConfirmTrace:
    """What `_consume_reset_token` learned about WHY a confirm failed, handed back beside the
    exception rather than on it.

    That separation is the FR-529 guarantee and it is structural: a `SafeAPIError` is what the
    GraphQL layer turns into the response, so a class carried on it could one day reach a caller.
    This object is read by `_record_failed_reset_confirm` and by nothing that builds a response.

    It also holds NO token material, by construction. The only things it can carry are a class
    from a closed enum and a user id. The recorder is never given the token, its fingerprint or
    its masked form, so it cannot write them.
    """

    outcome: ResetConfirmOutcome | None = None
    customer_user_id: int | None = None

    def resolved(self, customer_user_id: int) -> None:
        """The token row exists, is live and belongs to this user. Called as soon as that is
        known, so that even a failure nobody classified (a database error, a hasher error) names
        the account whose link was being used."""
        self.customer_user_id = customer_user_id

    def refused(self, outcome: ResetConfirmOutcome, *, customer_user_id: int | None = None) -> None:
        self.outcome = outcome
        if customer_user_id is not None:
            self.customer_user_id = customer_user_id

    def failed_unexpectedly(self) -> None:
        self.outcome = ResetConfirmOutcome.INTERNAL_ERROR


# --- who the row says did it -----------------------------------------------------------------
# The row must let an operator ask "every failed confirm from this source" without the table
# holding the address itself: the draft privacy policy promises that rate-limit counters expire
# within an hour and that audit records name who acted by an internal identifier. So the actor id
# is a KEYED, DAILY-ROTATING PSEUDONYM of the source bucket, `src:v1:<32 hex>`:
#
#   salted_hmac(key_salt = "...audit_source.v1", value = "<UTC date>|<bucket>", SHA-256)[:32]
#
# i.e. Django's own derivation, key = SHA-256(key_salt + SECRET_KEY), then HMAC-SHA-256 under that
# key. It is structurally unlike `_fingerprint` (HMAC keyed by SECRET_KEY itself over the value),
# so no pseudonym can ever coincide with a credential fingerprint, whatever string is hashed.
#
# - keyed, so a table dump alone does not reveal addresses and a rainbow table of IPv4 space is
#   useless without SECRET_KEY;
# - rotating, so the same address is a different pseudonym tomorrow and a source cannot be
#   followed across days from the table alone;
# - versioned (`v1`), so a future change of scheme is recognisable in the stored value;
# - computed from the same /64-bucketed string `client_ip()` gives the budget, so the record and
#   the budget agree about what "one source" is.
#
# ROTATING SECRET_KEY ORPHANS EVERY OLDER ROW: the pseudonym is recomputed from the CURRENT key
# (`SECRET_KEY_FALLBACKS` is not consulted), so rows written before the rotation can no longer be
# found from an address; they remain, unreadable as sources, until retention removes them.
#
# It is STILL PERSONAL DATA: whoever holds SECRET_KEY can test a candidate address against the
# table, which is exactly what `manage.py failed_reset_confirms --ip` does. Pseudonymising is not
# anonymising, and it is no substitute for a retention period for these rows, which is a
# separate open ticket (17tnw2b9dp1). The two fixed labels below carry no address at all.
_AUDIT_SOURCE_KEY_SALT = "selahcue_api.apps.accounts.audit_source.v1"
AUDIT_SOURCE_PREFIX = "src:"
AUDIT_SOURCE_VERSIONED_PREFIX = "src:v1:"
# `client_ip()` returns "unknown" when REMOTE_ADDR is absent; this module substitutes
# UNRESOLVED_CLIENT_IP when the resolver had no request at all. Neither is an address.
_UNATTRIBUTED_SOURCES = frozenset({UNRESOLVED_CLIENT_IP, "unknown"})


def _audit_source_day() -> date:
    """The UTC date a pseudonym is minted for. A seam: tests move it to show rotation."""
    return djtz.now().astimezone(dt_timezone.utc).date()


def audit_source_pseudonym(source: str, day: date | None = None) -> str:
    """The actor id a failed-confirm row carries for `source` (an already-bucketed address, as
    `client_ip()` returns it) on `day` (UTC; default today)."""
    if source in _UNATTRIBUTED_SOURCES:
        return f"{AUDIT_SOURCE_PREFIX}{source}"
    value = f"{(day or _audit_source_day()).isoformat()}|{source}"
    digest = salted_hmac(_AUDIT_SOURCE_KEY_SALT, value, algorithm="sha256").hexdigest()
    return AUDIT_SOURCE_VERSIONED_PREFIX + digest[:32]


def audit_source_today() -> date:
    """Today's UTC date as the writer sees it: the operator command's default day, so the command
    and the rows can never disagree about which day "today" is."""
    return _audit_source_day()


def audit_source_pseudonym_for_address(address: str, day: date | None = None) -> str:
    """Operator-facing: the pseudonym for a LITERAL address, bucketed exactly as `client_ip()`
    buckets it (IPv4 as is, IPv6 to its /64). Raises ValueError for text that is not an address.
    Used by `manage.py failed_reset_confirms`; from a shell:

        from selahcue_api.apps.accounts.services import audit_source_pseudonym_for_address
        audit_source_pseudonym_for_address("203.0.113.5")
        # then: AuditEvent.objects.filter(action=RESET_CONFIRM_FAILED_ACTION, actor_id=<that>)
    """
    return audit_source_pseudonym(bucket_for_throttling(ipaddress.ip_address(address.strip())), day)


# --- bounded reporting for the trace itself ---------------------------------------------------
_TRACE_REPORT_INTERVAL_SECONDS = 60.0
# Long enough for the longest first-event detail (outcome, pseudonym and reason) without cutting
# the reason off mid-word.
_TRACE_REPORT_DETAIL_MAX = 160
# How many distinct skipped account ids one report names. The set is capped, so the tally stays
# bounded however many accounts are probed.
_TRACE_REPORT_ACCOUNTS_MAX = 20


class _SuppressedTally:
    """Counts events and releases ONE report a minute: how many since the last report, what the
    first of them looked like, and up to `_TRACE_REPORT_ACCOUNTS_MAX` distinct account ids.

    State is a lock, one int, one string capped at `_TRACE_REPORT_DETAIL_MAX` characters, one
    float and a set of at most `_TRACE_REPORT_ACCOUNTS_MAX` ints, whatever the event rate and
    however many distinct sources or accounts there are. A per-source map would be keyed by
    attacker-chosen values on an unauthenticated endpoint -- the unbounded growth the repo
    forbids -- and would grow fastest exactly during the flood this reports on.

    WHEN COUNTS FLUSH: the FIRST event is released at once (the first skipped row is reported as
    "skipped 1"). After that, events are only counted; the count, with the first of them
    described, is released by the next event to arrive once the interval has passed. So a burst
    followed by silence is reported when the next event arrives, not before.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Test seam."""
        with self._lock:
            self._count = 0
            self._first = ""
            self._accounts: set[int] = set()
            self._last_report = float("-inf")

    def note(self, detail: str, account_id: int | None = None) -> tuple[int, str, list[int]] | None:
        """Record one event. Returns (count since the last report, first detail, the distinct
        account ids seen, capped) when a report is due, resetting the tally, else None."""
        now = time.monotonic()
        with self._lock:
            if self._count == 0:
                self._first = detail[:_TRACE_REPORT_DETAIL_MAX]
            self._count += 1
            if account_id is not None and len(self._accounts) < _TRACE_REPORT_ACCOUNTS_MAX:
                self._accounts.add(account_id)
            if now - self._last_report < _TRACE_REPORT_INTERVAL_SECONDS:
                return None
            released = (self._count, self._first, sorted(self._accounts))
            self._count = 0
            self._first = ""
            self._accounts = set()
            self._last_report = now
            return released


class _AccountCeilings:
    """Per-worker, per-account fixed windows: the outage stand-in for the per-account allowance.

    Process-local on purpose (the shared store is what is down), so with N workers the real
    allowance is N times the limit. MEMORY IS BOUNDED BY CONSTRUCTION: at most `max_entries`
    accounts are tracked, and starting a window for a new account first evicts the
    least-recently-started one. An account keyed here is a real account (the id comes from a
    token row that exists), never an attacker-chosen string. Eviction forgets an account's count,
    so a caller who can name more than `max_entries` accounts in an hour gets a fresh window for
    the ones evicted: a bounded loss of protection, chosen over unbounded growth.
    """

    def __init__(self, *, setting_name: str, default: tuple[int, int], max_entries: int):
        self._setting_name = setting_name
        self._default = default
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._windows: OrderedDict[int, list[float]] = OrderedDict()

    def reset(self) -> None:
        """Test seam."""
        with self._lock:
            self._windows.clear()

    def claim(self, account_id: int) -> bool:
        """Claim one unit of `account_id`'s window. False means: skip the row."""
        limit, window = getattr(settings, self._setting_name, self._default)
        limit, window = int(limit), float(window)
        now = time.monotonic()
        with self._lock:
            entry = self._windows.get(account_id)
            if entry is None or now - entry[0] >= window:
                entry = [now, 0]
                self._windows[account_id] = entry
                self._windows.move_to_end(account_id)
                while len(self._windows) > self._max_entries:
                    self._windows.popitem(last=False)
            if entry[1] >= limit:
                return False
            entry[1] += 1
            return True


_trace_lost_tally = _SuppressedTally()
_trace_skipped_tally = _SuppressedTally()
# The outage stand-ins, one per kind of outcome (see `_trace_skip_reason`). Same mechanism as the
# send ceilings above; only `claim()` is used, the reporting is the tally's.
_reset_confirm_trace_ceiling = _DegradedSendCeiling(
    label="password-reset-confirm-trace",
    setting_name="SELAHCUE_RESET_CONFIRM_TRACE_DEGRADED_CEILING",
    default=RESET_CONFIRM_TRACE_DEGRADED_CEILING,
)
_reset_confirm_trace_account_ceilings = _AccountCeilings(
    setting_name="SELAHCUE_RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING",
    default=RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING,
    max_entries=RESET_CONFIRM_TRACE_ACCOUNT_TABLE_MAX,
)


def _reset_trace_reporting() -> None:
    """Test seam: forget the trace tallies and the outage ceilings' windows."""
    _trace_lost_tally.reset()
    _trace_skipped_tally.reset()
    _reset_confirm_trace_ceiling.reset()
    _reset_confirm_trace_account_ceilings.reset()


def _trace_skip_reason(trace: _ResetConfirmTrace, limiter_degraded: bool) -> str | None:
    """Why this failure's ROW must not be written, or None to write it. Never affects the
    response.

    TWO allowances, because one shared counter lets a flood blind the trace to exactly the
    outcomes it exists for. Unauthenticated noise (an unknown or malformed token, or an internal
    error before any account was identified) costs nothing to produce and spends the SHARED
    brake. An outcome that NAMES AN ACCOUNT (consumed, expired, wrong purpose, a rejected
    password, or an internal error after the token validated) is what a probe of a skimmed token
    looks like, so it spends only that account's own allowance, keyed by user id: a stranger
    cannot fill another account's allowance (they would need that account's own token), and the
    key space is bounded by real accounts. A SEPARATE shared bucket for named outcomes would not
    do: anyone can mint wrong-purpose noise from tokens of accounts they own.

    Healthy store: the budget lives in the shared store. Store down -- either the per-source
    budget already failed open, or this very call finds the store unavailable -- a process-local
    ceiling of the same shape stands in. Once the per-source budget has failed open the store is
    not asked again (one round trip per request, so a stalled Redis costs one timeout, not two).
    """
    account_id = trace.customer_user_id
    if account_id is None:
        budget = (
            RESET_CONFIRM_TRACE_SCOPE,
            "all",
            "SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE",
            RESET_CONFIRM_TRACE_BUDGET,
        )

        def claim_in_process() -> bool:
            return _reset_confirm_trace_ceiling.claim()

        spent = "shared brake spent"
        spent_in_outage = "outage ceiling spent"
    else:
        budget = (
            RESET_CONFIRM_TRACE_ACCOUNT_SCOPE,
            str(account_id),
            "SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT",
            RESET_CONFIRM_TRACE_ACCOUNT_BUDGET,
        )

        def claim_in_process() -> bool:
            return _reset_confirm_trace_account_ceilings.claim(account_id)

        spent = "account allowance spent"
        spent_in_outage = "account outage allowance spent"
    if not limiter_degraded:
        outcome = spend_budget(*budget, report_denial=False)
        if outcome is BudgetOutcome.DENIED:
            return spent
        limiter_degraded = outcome is BudgetOutcome.STORE_UNAVAILABLE
    if limiter_degraded and not claim_in_process():
        return spent_in_outage
    return None


def _note_lost_trace(error: Exception, outcome: ResetConfirmOutcome, source: str) -> None:
    """Count a trace row that could not be written or decided, and report it at most once a
    minute: the count, and the exception CLASS, outcome and pseudonym of the first. No traceback
    (see `_record_failed_reset_confirm`). Never raises: if even this fails there is nothing left
    to report with, and the response must not change."""
    try:
        try:
            label = audit_source_pseudonym(source)
        except Exception:  # noqa: BLE001 -- the pseudonym is what may have failed
            label = "unlabelled"
        released = _trace_lost_tally.note(f"{type(error).__name__} outcome={outcome.value} source={label}")
        if released is not None:
            count, first, _accounts = released
            logger.warning(
                "could not write the audit row for %d failed password-reset confirm(s) since the "
                "last report (first: %s). The callers' responses were unchanged; those attempts "
                "have no trace. Further reports suppressed for %.0fs.",
                count,
                first,
                _TRACE_REPORT_INTERVAL_SECONDS,
            )
    except Exception:  # noqa: BLE001 -- see the docstring
        pass


def _trace_failed_confirm(trace: _ResetConfirmTrace, source: str, limiter_degraded: bool) -> None:
    """Write the row for one failed confirm unless it is being skipped. NEVER RAISES: the whole
    body is protected, not just the INSERT -- a malformed setting, a failing ceiling or a failing
    log call is counted as a lost row like a failing write, and the caller still gets the answer
    they would have got without the trace."""
    outcome = trace.outcome or ResetConfirmOutcome.UNCLASSIFIED
    try:
        reason = _trace_skip_reason(trace, limiter_degraded)
        if reason is None:
            _record_failed_reset_confirm(trace, source)
            return
        released = _trace_skipped_tally.note(
            f"outcome={outcome.value} source={audit_source_pseudonym(source)} reason={reason}",
            trace.customer_user_id,
        )
        if released is not None:
            count, first, accounts = released
            logger.warning(
                "skipped %d audit row(s) for failed password-reset confirms since the last report "
                "(first: %s%s). The callers' responses were unchanged; those attempts have no "
                "trace. Further reports suppressed for %.0fs.",
                count,
                first,
                f"; accounts {accounts}" if accounts else "",
                _TRACE_REPORT_INTERVAL_SECONDS,
            )
    except Exception as error:  # noqa: BLE001 -- see the docstring
        _note_lost_trace(error, outcome, source)


def _record_failed_reset_confirm(trace: _ResetConfirmTrace, source: str) -> None:
    """Write the audit row for one failed confirm. Best effort, and never raises.

    WHAT THE ROW HOLDS: the outcome class, a per-attempt id, the timestamp the audit table adds
    itself, the owning user's id when the token row resolved, and as the actor the pseudonym of
    the source (see `audit_source_pseudonym`). The address itself is NOT stored, here or in
    `after`. WHAT IT MUST NEVER HOLD: the raw token, its fingerprint, its at-rest hash or its
    masked form (a reset token skimmed from a mailbox or a log and polled until the moment is
    right is exactly the scenario this trace is for, and a fingerprint in the trace would turn
    the trace into a way to confirm a guess). That is kept by construction -- this function is
    never handed any of them -- and asserted by
    `test_no_token_material_reaches_any_audit_column_or_log_line_of_a_failed_confirm`.
    `request_id` is a fresh random id for the attempt, NOT derived from the token, unlike the
    success row's (which stores the masked token).

    The actor is ANONYMOUS and the pseudonym is the actor id, so the audit table's
    `(actor_id, created_at)` index answers "every failed confirm from this source today".

    WHERE IT RUNS: after `_consume_reset_token` has returned control, i.e. after its transaction
    rolled back. Written inside, the row would be rolled back with the failure it describes.
    The write has its own `atomic()`: with no enclosing transaction (production -- the project
    sets no ATOMIC_REQUESTS) that is a real transaction, so a half-written row cannot be left
    behind; inside an enclosing one (every pytest-django test) it is a savepoint, so a failed
    INSERT cannot poison the caller's transaction either. No `_require_autocommit`-style guard
    like the licence writers have: that one refuses, because a lost DENIED row there is a lost
    compliance record; here the trace is best effort by design and refusing a password reset
    because its trace might roll back would invert the priority (and fail every test, which all
    run inside pytest-django's transaction).

    WHY IT SWALLOWS: the caller must get the answer they would have got without the trace. A 500
    in its place would turn an audit outage into a changed contract on a path whose whole job
    is to say one thing. The loss is reported instead (`_note_lost_trace`), once a minute with a
    count, and WITHOUT the traceback: this runs while the original failure is being handled, so
    a chained traceback would carry frames whose locals hold the raw token and the submitted
    password to any log handler that captures locals.

    WHAT IT DOES NOT COVER: a call refused by the budget never reaches this (the budget is spent
    before the token is read, and a row per refused request would turn the flood the budget stops
    into database writes; the shared guard already logs a sustained run of refusals).
    """
    outcome = trace.outcome or ResetConfirmOutcome.UNCLASSIFIED
    user_id = trace.customer_user_id
    try:
        actor_id = audit_source_pseudonym(source)
        with transaction.atomic():
            record_audit_event(
                ActorContext(kind=ActorKind.ANONYMOUS, actor_id=actor_id),
                action=RESET_CONFIRM_FAILED_ACTION,
                target_type="customer_user" if user_id is not None else "credential_token",
                target_id=str(user_id) if user_id is not None else "unresolved",
                request_id=uuid.uuid4().hex,
                result=AuditResult.DENIED,
                source_surface=ACCOUNT_AUDIT_SURFACE,
                after={"outcome": outcome.value},
            )
    except Exception as error:  # noqa: BLE001 -- see "WHY IT SWALLOWS"
        _note_lost_trace(error, outcome, source)


def _dead_token_outcome(token: CredentialToken, now) -> ResetConfirmOutcome:
    """Label why a token that exists cannot be used. Labelling only: the guard that REFUSES it
    stays where it is, in `_consume_reset_token`, and does not call this to decide anything."""
    if token.purpose != CredentialTokenPurpose.PASSWORD_RESET:
        return ResetConfirmOutcome.WRONG_PURPOSE
    if token.consumed_at is not None:
        return ResetConfirmOutcome.CONSUMED
    if token.expires_at <= now:
        return ResetConfirmOutcome.EXPIRED
    return ResetConfirmOutcome.UNCLASSIFIED


def confirm_password_reset(
    raw_token: str, new_password: str, client_ip: str = ""
) -> ConfirmPasswordResetResult:
    """Consume a PASSWORD_RESET token, set the new password, and revoke ALL of the user's ACTIVE
    sessions (invalidation on password change).

    Errors, and why they differ (FR-551, DEC-012 (a)):

    - EVERY token failure — malformed, unknown, wrong-purpose, consumed, expired — is one
      collapsed VALIDATION_FAILED, mutually indistinguishable. Unchanged (FR-529 / CON-P6).
    - A bad password behind a LIVE token is PASSWORD_INVALID, so the caller is told the one
      thing they can act on. Reachable only after the token has been validated.

    Spends a per-client-IP budget FIRST — 86akcmfd4, DEC-013's required follow-up — before the
    token is even looked at. This endpoint was previously reachable at an unlimited rate, which
    is what let a token-guessing or timing probe repeat indefinitely. `RATE_LIMITED` cannot
    become a sixth, more-informative token-failure code: it is decided purely by request COUNT
    from `client_ip`, checked before the token lookup runs, so it fires identically whether the
    token offered was live, dead, or never existed. It does not touch the FIVE-way collapse
    above, and it is not reachable from behind a validated token any more than in front of one.

    Every failure that gets past that budget leaves one audit row (86ak5r2pt), written by
    `_record_failed_reset_confirm` AFTER the transaction below has rolled back, unless a flood
    brake skips the ROW (never the response; see `_trace_skip_reason`). The class it records
    travels in a `_ResetConfirmTrace`, never on the exception, so the five collapsed classes stay
    indistinguishable in the RESPONSE while being told apart in the trace.
    """
    if not client_ip:
        _report_unresolved_client_ip("confirm_password_reset")
    source = client_ip or UNRESOLVED_CLIENT_IP
    # `_reporting_outage`: a fail-open is still a permit for the RESPONSE, but it means nothing is
    # bounding how many trace rows the caller can cause (see `_trace_skip_reason`).
    limiter_degraded = enforce_budget_reporting_outage(
        "password_reset_confirm_ip",
        source,
        "SELAHCUE_THROTTLE_RESET_CONFIRM",
        RESET_CONFIRM_IP_BUDGET,
    )
    trace = _ResetConfirmTrace()
    try:
        return _consume_reset_token(raw_token, new_password, trace)
    except SafeAPIError:
        _trace_failed_confirm(trace, source, limiter_degraded)
        raise
    except Exception:
        # Not a coded refusal: a database error, a hasher error. The caller's answer is whatever
        # the view makes of it (the same masked answer a dead token gets); the trace must not
        # depend on the failure being a tidy one.
        trace.failed_unexpectedly()
        _trace_failed_confirm(trace, source, limiter_degraded)
        raise


def _live_reset_token(
    fingerprint: str, trace: _ResetConfirmTrace, *, for_update: bool = False
) -> CredentialToken:
    """Read and validate current liveness; the write-phase caller already owns atomic().

    Read the clock AFTER the query returns: hashing or waiting for a row lock can carry
    a formerly live token past expiry. Both preflight and the locked read use the same
    collapsed-token checks, while only the latter authorizes the password write.
    """
    tokens = CredentialToken.objects
    if for_update:
        # Keep the existing joined user lock as well as the token lock. Do not write a
        # stale preflight user instance after concurrent login/reset work has completed.
        tokens = tokens.select_for_update().select_related("customer_user")
    try:
        token = tokens.get(token_fingerprint=fingerprint)
    except CredentialToken.DoesNotExist as error:
        trace.refused(ResetConfirmOutcome.UNKNOWN_TOKEN)
        raise _validation_error() from error
    if not hmac.compare_digest(token.token_fingerprint, fingerprint):
        trace.refused(ResetConfirmOutcome.UNKNOWN_TOKEN)
        raise _validation_error()
    now = djtz.now()
    if (
        token.purpose != CredentialTokenPurpose.PASSWORD_RESET
        or token.consumed_at is not None
        or token.expires_at <= now
    ):
        trace.refused(_dead_token_outcome(token, now), customer_user_id=token.customer_user_id)
        raise _validation_error()
    trace.resolved(token.customer_user_id)
    return token


def _consume_reset_token(
    raw_token: str, new_password: str, trace: _ResetConfirmTrace
) -> ConfirmPasswordResetResult:
    """Preflight a live token, hash off-lock, then revalidate and write atomically.

    86ak5qy3p chooses off-lock PBKDF2 rather than retaining CPU work under the token/user
    locks. Initial token validation must precede password policy AND hashing (FR-551,
    FR-529). It is only a preflight: another reset or expiry can invalidate the token while
    hashing, so a fresh locked liveness check below remains the authority to consume it.
    This service opens no transaction around hashing; caller-owned outer transactions
    remain caller-owned (production does not enable ATOMIC_REQUESTS).
    """
    token_value = (raw_token or "").strip()
    if not token_value:
        trace.refused(ResetConfirmOutcome.MALFORMED_TOKEN)
        raise _validation_error()
    try:
        token_value.encode("utf-8")
    except UnicodeEncodeError:
        # Lone surrogates (JSON "\ud800" escapes): no token can look like that, and hashing it
        # would raise. Same collapsed answer as any other malformed token.
        trace.refused(ResetConfirmOutcome.MALFORMED_TOKEN)
        raise _validation_error() from None
    fingerprint = _fingerprint(token_value)
    token = _live_reset_token(fingerprint, trace)
    # A LIVE link may expose PASSWORD_INVALID (DEC-017); a dead link never reaches this.
    # Rejection happens before any consume, so it cannot burn the caller's reset link.
    # The write transaction still owns rollback of consume/password/session/audit changes
    # if a later operation fails; see the existing failed-reset rollback regression.
    try:
        _validate_password(new_password, code=ErrorCode.PASSWORD_INVALID)
    except SafeAPIError:
        trace.refused(ResetConfirmOutcome.PASSWORD_REJECTED, customer_user_id=token.customer_user_id)
        raise
    password_hash = make_password(new_password)
    with transaction.atomic():
        token = _live_reset_token(fingerprint, trace, for_update=True)
        now = djtz.now()
        token.consumed_at = now
        token.save(update_fields=["consumed_at"])
        user = token.customer_user
        user.password_hash = password_hash
        user.password_changed_at = now
        user.failed_login_count = 0
        user.locked_until = None
        user.save(
            update_fields=[
                "password_hash",
                "password_changed_at",
                "failed_login_count",
                "locked_until",
                "updated_at",
            ]
        )
        CustomerSession.objects.filter(
            customer_user=user, status=CustomerSessionStatus.ACTIVE
        ).update(status=CustomerSessionStatus.REVOKED, revoked_at=now, updated_at=now)
        record_audit_event(
            _customer_actor(user),
            action="customer_user.password_reset_completed",
            target_type="customer_user",
            target_id=str(user.id),
            request_id=token.masked_token,
            source_surface=ACCOUNT_AUDIT_SURFACE,
            after={},
        )
    return ConfirmPasswordResetResult(reset=True)
