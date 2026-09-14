from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone as djtz
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
from selahcue_api.apps.audit.services import record_audit_event
# Safe at module scope: `throttling.guards` depends only on the cache, the pure limiter and
# the error enum — nothing in accounts — so this cannot close an import cycle.
from selahcue_api.apps.throttling.guards import (
    enforce_budget,
    enforce_budget_reporting_outage,
)
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
    device_limit: int = 1
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
    if data.seat_limit < 1 or data.device_limit < 1:
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
            device_limit=data.device_limit,
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
                "device_limit": customer.device_limit,
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
# Memory is three module-level scalars, deliberately NOT a per-address or per-IP map: a map
# here would be keyed by attacker-chosen values on an unauthenticated endpoint, which is the
# unbounded growth the repo forbids, and it would grow fastest exactly during the flood.
RESEND_DEGRADED_SEND_CEILING = (20, 3600)
_DEGRADED_SEND_LOG_INTERVAL_SECONDS = 60.0
# A lock, where the log suppressors above accept a benign race. Those cost at most a spare
# log line; this is a CEILING, and the flood it bounds is concurrent by definition, so an
# unsynchronised read-modify-write would let it be overspent by however many workers raced.
_degraded_send_lock = threading.Lock()
_degraded_window_started = float("-inf")
_degraded_window_sends = 0
_last_degraded_send_log = float("-inf")


def _degraded_send_ceiling() -> tuple[int, float]:
    """(limit, window_seconds) for the degraded ceiling, read per call like the floor."""
    limit, window = getattr(
        settings, "SELAHCUE_RESEND_DEGRADED_SEND_CEILING", RESEND_DEGRADED_SEND_CEILING
    )
    return int(limit), float(window)


def _reset_degraded_send_window() -> None:
    """Test seam: forget the current window and the last report, so a test can observe the
    first skip and the first warning deterministically without waiting out either interval."""
    global _degraded_window_started, _degraded_window_sends, _last_degraded_send_log
    with _degraded_send_lock:
        _degraded_window_started = float("-inf")
        _degraded_window_sends = 0
    _last_degraded_send_log = float("-inf")


def _claim_degraded_send() -> bool:
    """Claim one unit of the degraded ceiling. False means: do not send, and do not mint.

    A fixed window on `time.monotonic()` — the same shape as the store-backed limiter, so the
    degraded path is not a second rate limiter with its own semantics to reason about.

    Charged on EVERY call during an outage, including calls for addresses that could never
    send. Charging only senders would be cheaper and is wrong: the ceiling is shared, and an
    attacker can watch it drain through their own inbox, so a ceiling that only bit for real
    accounts would leak whether an address has a verification pending — one probe, one bit.
    That is the defect `resend_email_verification`'s docstring already rules out for the three
    real budgets, and this stands in for them.
    """
    limit, window = _degraded_send_ceiling()
    global _degraded_window_started, _degraded_window_sends
    now = time.monotonic()
    with _degraded_send_lock:
        if now - _degraded_window_started >= window:
            _degraded_window_started = now
            _degraded_window_sends = 0
        if _degraded_window_sends >= limit:
            return False
        _degraded_window_sends += 1
        return True


def _report_degraded_send_skipped() -> None:
    """Warn — at most once per interval — that mail is being dropped, and why.

    Rate limited for the same reason every other report on this path is: one line per dropped
    send at flood rate is the unbounded logging the repo forbids. The throttle store logs its
    own fail-open; this line carries the part that one cannot know, which is that the
    fail-open has started COSTING something.
    """
    global _last_degraded_send_log
    now = time.monotonic()
    if now - _last_degraded_send_log < _DEGRADED_SEND_LOG_INTERVAL_SECONDS:
        return
    _last_degraded_send_log = now
    limit, window = _degraded_send_ceiling()
    logger.warning(
        "resend-verification skipped a send: limiter unavailable, so all three budgets "
        "failed open and the process-local fallback ceiling (%d per %.0fs, PER WORKER) is "
        "spent. Callers still receive the normal accepted:true — the response must not "
        "reveal the outage — and no link was superseded, so an existing one still works. "
        "The remedy is to restore the rate-limit store; raising "
        "SELAHCUE_RESEND_DEGRADED_SEND_CEILING only buys more unmetered mail while it is "
        "down. Further reports suppressed for %.0fs.",
        limit,
        window,
        _DEGRADED_SEND_LOG_INTERVAL_SECONDS,
    )


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
                device_limit=1,
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


def verify_email(raw_token: str) -> VerifyEmailResult:
    """Consume an EMAIL_VERIFY token: mark the user ACTIVE + email_verified_at. Every failure
    (unknown / wrong-purpose / consumed / expired) collapses to VALIDATION_FAILED (no oracle)."""
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


def login(data: LoginData) -> LoginResult:
    """Authenticate email/password and mint a session. Unknown-email and wrong-password are
    indistinguishable (both UNAUTHENTICATED, equal timing). Unverified/disabled → POLICY_DENIED
    only AFTER a correct password (so state leaks only to the real owner)."""
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
            source_surface=ACCOUNT_AUDIT_SURFACE,
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

    Spends a per-client-IP budget FIRST, before the email is even validated — 86akcmfd4, DEC-013's
    required follow-up. The mint-vs-no-mint branch below is what DEC-013 measured a ~0.437ms gap
    on; this does not close that gap (see the comment on the `else` branch for why not), it bounds
    how many times one source can sample it. The budget is spent UNCONDITIONALLY, before the
    existence check, for the same reason the resend budgets are: a limiter that only bit for real
    accounts would itself be an existence oracle. `RATE_LIMITED` cannot leak anything about the
    email either way — it is decided purely by request COUNT from `client_ip`, before any
    existence-dependent branch runs, so a throttled caller learns nothing about the email they sent.
    """
    if not client_ip:
        _report_unresolved_client_ip("request_password_reset")
    enforce_budget(
        "password_reset_request_ip",
        client_ip or UNRESOLVED_CLIENT_IP,
        "SELAHCUE_THROTTLE_RESET_REQUEST",
        RESET_REQUEST_IP_BUDGET,
    )
    normalized = _require_valid_email(email)
    fingerprint = _email_fingerprint(normalized)
    now = djtz.now()
    with transaction.atomic():
        user = CustomerUser.objects.filter(email_fingerprint=fingerprint).first()
        if user is not None:
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
    """
    if not client_ip:
        _report_unresolved_client_ip("confirm_password_reset")
    enforce_budget(
        "password_reset_confirm_ip",
        client_ip or UNRESOLVED_CLIENT_IP,
        "SELAHCUE_THROTTLE_RESET_CONFIRM",
        RESET_CONFIRM_IP_BUDGET,
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
            token.purpose != CredentialTokenPurpose.PASSWORD_RESET
            or token.consumed_at is not None
            or token.expires_at <= now
        ):
            raise _validation_error()
        # FR-551 — THE ORDER OF THESE TWO CHECKS IS THE FIX. DO NOT MOVE THIS ABOVE THE
        # TOKEN LOOKUP.
        #
        # The token is now known live, so the caller has proved possession of a working link
        # and may safely be told that it is their PASSWORD that is wrong. Run before this
        # block, the password check reached everyone — and, raising the same collapsed
        # VALIDATION_FAILED as every token failure, told a user with a perfectly good link
        # that the link was broken. They fetched a fresh one, retyped the same short
        # password, and looped with no exit and no clue (DEC-012 (a)).
        #
        # WHY THIS LEAKS NOTHING is argued ONCE, beside `ErrorCode.PASSWORD_INVALID` in
        # `selahcue_api/graphql/errors.py`. Do not restate it here: the argument was being
        # maintained in four places, and by the first review round one copy had drifted.
        #
        # ON THE PLACEMENT RELATIVE TO THE CONSUME BELOW — read this before "tidying" it.
        # A rejected password does not burn the user's link. That guarantee comes from the
        # enclosing `transaction.atomic()`, which rolls the consume back on the raise; it
        # does NOT come from this line sitting above `token.consumed_at`. The two are
        # redundant, and the transaction is the one doing the work.
        #
        # Said plainly because an earlier version of this comment claimed the opposite — and
        # with numbers, because the version after that understated them. Measured over the
        # whole API suite, at 523 tests:
        #
        #   this call moved BELOW the consume, `atomic()` intact   523 passed — nothing notices
        #   `atomic()` removed, this call left where it is         1 failed
        #   BOTH                                                   5 failed
        #
        # Two reviewers measured the same shape independently on the 520-test tree that went
        # into review: 520 passed / 1 failed / 4 failed. The counts move as tests are added;
        # the shape is what matters, and it has now been reproduced three times.
        #
        # So the placement is inert while the transaction holds, and removing the transaction
        # is loud whether or not the placement goes with it. Keep the placement — it is
        # defence in depth for the day the transaction boundary is refactored away — but do
        # not believe the link-preservation property is tested by its position. It is tested
        # through `atomic()`, by `test_a_failed_reset_rolls_back_the_consume_and_the_password`
        # in the auth slice.
        _validate_password(new_password, code=ErrorCode.PASSWORD_INVALID)
        token.consumed_at = now
        token.save(update_fields=["consumed_at"])
        user = token.customer_user
        user.password_hash = make_password(new_password)
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
