from uuid import uuid4

from django.db import models
from django.db.models import F, Q

from selahcue_api.apps.usage.contracts import ReservationState

from .observation_contracts import (
    Attribution, DGCompletion, HealthReason, ObservationIssue, RetentionKind, ScanPurpose, ScanState,
    UsageFailureCode, UsageHealthState, UsageProfile,
)

OPEN_STATES = (ReservationState.RESERVED.value, ReservationState.ISSUED.value)


class UsageWeek(models.Model):
    org = models.ForeignKey("selahcue_accounts.CustomerOrg", on_delete=models.PROTECT)
    week_start_local = models.DateField()
    tz_name = models.CharField(max_length=64)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    # A westward transition can start accounting before the first unused local Monday.
    admissions_start_at = models.DateTimeField()
    counted_from = models.DateTimeField()
    high_water_rank = models.PositiveIntegerField()
    stt_seconds_settled = models.PositiveBigIntegerField(default=0)
    notes_settled = models.PositiveBigIntegerField(default=0)
    stt_seconds_carried_debt = models.PositiveBigIntegerField(default=0)
    notes_carried_debt = models.PositiveBigIntegerField(default=0)
    # Opening limits cap carried debt for the life of this row. High-water limits
    # measure overrun and can change only on an upgrade to a higher rank.
    opening_stt_seconds_limit = models.PositiveBigIntegerField()
    opening_notes_limit = models.PositiveBigIntegerField()
    high_water_stt_seconds_limit = models.PositiveBigIntegerField()
    high_water_notes_limit = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "week_start_local"], name="usage_week_org_local_uniq"),
            models.CheckConstraint(
                condition=(
                    Q(starts_at__lte=F("counted_from"), counted_from__lt=F("ends_at"))
                    & Q(starts_at__lte=F("admissions_start_at"), admissions_start_at__lt=F("ends_at"))
                ),
                name="usage_week_valid_bounds",
            ),
        ]
        indexes = [models.Index(fields=["org", "-starts_at"], name="usage_week_org_starts_idx")]


class UsageReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    org = models.ForeignKey("selahcue_accounts.CustomerOrg", on_delete=models.PROTECT)
    license = models.ForeignKey("selahcue_license_keys.AppLicenseKey", on_delete=models.PROTECT)
    device = models.ForeignKey("selahcue_devices.Device", on_delete=models.PROTECT)
    week = models.ForeignKey(UsageWeek, on_delete=models.PROTECT, related_name="reservations")
    provider_mapping = models.ForeignKey(
        "selahcue_providers.ProviderCredential", on_delete=models.PROTECT, null=True,
    )
    meter = models.CharField(max_length=5, choices=[("stt", "Transcription"), ("notes", "Notes")])
    units = models.PositiveIntegerField()
    state = models.CharField(max_length=8, choices=[(state.value, state.value) for state in ReservationState])
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=64)
    admitted_at = models.DateTimeField()
    authorized_from = models.DateTimeField()
    authorized_until = models.DateTimeField()
    issued_at = models.DateTimeField(null=True, blank=True)
    last_minted_at = models.DateTimeField(null=True, blank=True)
    renews = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "meter", "idempotency_key"], name="usage_res_org_meter_key_uniq"),
            models.CheckConstraint(
                condition=Q(meter="stt", units=300) | Q(meter="notes", units=1, renews__isnull=True),
                name="usage_res_fixed_meter_units",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state__in=[state.value for state in ReservationState])
                    & ~Q(meter="notes", state=ReservationState.ISSUED)
                    & Q(retry_count=0)
                ),
                name="usage_res_valid_state",
            ),
            models.CheckConstraint(
                condition=Q(
                    admitted_at__lte=F("authorized_from"),
                    authorized_from__lt=F("authorized_until"),
                    admitted_at__lt=F("expires_at"),
                ),
                name="usage_res_valid_timing",
            ),
        ]
        indexes = [
            models.Index(fields=["week"], condition=Q(state__in=OPEN_STATES), name="usage_res_open_week_idx"),
            models.Index(
                fields=["org", "expires_at"], condition=Q(state=ReservationState.RESERVED.value),
                name="usage_res_expiry_idx",
            ),
        ]


class NoteDeliveryCredit(models.Model):
    class Reason(models.TextChoices):
        CONTENT_LOST = "CONTENT_LOST", "Content lost"

    reservation = models.OneToOneField(
        UsageReservation, on_delete=models.PROTECT, related_name="delivery_credit",
    )
    note_job_id = models.UUIDField(unique=True)
    original_week = models.ForeignKey(UsageWeek, on_delete=models.PROTECT, related_name="delivery_credits")
    units = models.PositiveIntegerField(default=1)
    observed_at = models.DateTimeField()
    reason = models.CharField(max_length=12, choices=Reason.choices, default=Reason.CONTENT_LOST)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(units=1, reason="CONTENT_LOST"), name="usage_credit_one_content_lost",
            ),
        ]


_ORG = "selahcue_accounts.CustomerOrg"
_POOL = "selahcue_providers.ProviderCapacityPool"
_EPOCH = "selahcue_providers.ScopePolicyEpoch"
_MAPPING = "selahcue_providers.ProviderCredential"
_HEALTH = "ProviderUsageHealthState"
_DG, _OA = "deepgram", "openai"


def _fk(target, *, nullable=False, **kwargs):
    return models.ForeignKey(target, on_delete=models.PROTECT, null=nullable, **kwargs)


def _one(target, *, nullable=False, **kwargs):
    return models.OneToOneField(target, on_delete=models.PROTECT, null=nullable, **kwargs)


def _text(max_length=256, *, nullable=False, **kwargs):
    return models.CharField(max_length=max_length, null=nullable, **kwargs)


def _enum(values, *, nullable=False, default=models.NOT_PROVIDED):
    values = tuple(values)
    return _text(
        max(len(v) for v in values), nullable=nullable, choices=[(v, v) for v in values], default=default,
    )


def _date():
    return models.DateTimeField(null=True)


def _digest():
    return _text(64, nullable=True)


def _uuid():
    return models.UUIDField(null=True)


def _check(name, condition):
    return models.CheckConstraint(name=f"usage_{name}", condition=condition)


def _uniq(name, *fields, **kwargs):
    return models.UniqueConstraint(name=f"usage_{name}", fields=fields, **kwargs)


def _index(name, *fields, **kwargs):
    return models.Index(name=f"usage_{name}", fields=fields, **kwargs)


def _all_null(*fields):
    return Q(**{f"{field}__isnull": True for field in fields})


def _all_set(*fields):
    return Q(**{f"{field}__isnull": False for field in fields})


def _pair(*fields):
    return _all_null(*fields) | _all_set(*fields)


def _health_shape():
    return (
        Q(state=UsageHealthState.CURRENT, reason__isnull=True)
        | Q(state=UsageHealthState.BLOCKED, reason=HealthReason.THRESHOLD)
        | (
            Q(state=UsageHealthState.UNRESOLVED, reason__isnull=False)
            & Q(reason__in=tuple(r for r in HealthReason if r != HealthReason.THRESHOLD))
        )
    )


class _ObservationRow(models.Model):
    created_at = models.DateTimeField()

    class Meta:
        abstract = True


class _MutableObservation(_ObservationRow):
    updated_at = models.DateTimeField()

    class Meta:
        abstract = True


class _UuidObservation(_MutableObservation):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    class Meta:
        abstract = True


class ProviderUsageHealthState(_MutableObservation):
    provider = _text(8, primary_key=True)
    revision = models.PositiveBigIntegerField(default=1)
    state = _enum(UsageHealthState, default=UsageHealthState.UNRESOLVED)
    reason = _enum(HealthReason, nullable=True, default=HealthReason.COVERAGE_MISSING)

    class Meta:
        constraints = [
            _check("provider_health_shape", Q(provider__in=(_DG, _OA), revision__gte=1) & _health_shape()),
        ]


class UsageScope(_MutableObservation):
    provider = _enum((_DG, _OA))
    parent_scope_id = _text()
    pool = _one(_POOL, nullable=True)
    normalization_revision = models.PositiveBigIntegerField(default=1)
    next_scan_generation = models.PositiveBigIntegerField(default=1)
    lane_fence = models.PositiveBigIntegerField(default=0)
    lane_scan = _fk("UsageScan", nullable=True, related_name="+")
    lane_page_ordinal = models.PositiveBigIntegerField(null=True)
    lane_lease_id = _uuid()
    lane_lease_until = _date()
    scheduling_turn = models.PositiveSmallIntegerField(default=0)
    last_served_at = _date()
    history_next_start = _date()
    attribution_after_record_id = models.PositiveBigIntegerField(null=True)

    class Meta:
        constraints = [
            _uniq("scope_parent", "provider", "parent_scope_id"),
            _check("scope_shape", Q(
                provider__in=(_DG, _OA), normalization_revision__gte=1,
                next_scan_generation__gte=1, scheduling_turn__lte=2,
            ) & _pair("lane_scan", "lane_page_ordinal", "lane_lease_id", "lane_lease_until")),
        ]


class UsageScan(_UuidObservation):
    scope = _fk(UsageScope)
    profile = _enum(UsageProfile)
    purpose = _enum(ScanPurpose)
    generation = models.PositiveBigIntegerField()
    requested_start = models.DateTimeField()
    requested_end = models.DateTimeField()
    started_at = models.DateTimeField()
    state = _enum(ScanState, default=ScanState.PARTIAL)
    page_ordinal = models.PositiveBigIntegerField(default=0)
    next_cursor = _text(4096, nullable=True)
    finished_at = _date()
    terminal_page_seen = models.BooleanField(default=False)
    failure_code = _enum(UsageFailureCode, nullable=True)
    replacement_not_before = _date()
    policy_epoch = _fk(_EPOCH, nullable=True)
    policy_digest = _digest()
    last_served_at = _date()

    class Meta:
        constraints = [
            _uniq("scan_generation", "scope", "generation"),
            _uniq("scan_unfinished", "scope", "profile", "requested_start", "requested_end",
                  condition=Q(state=ScanState.PARTIAL)),
            _check(
                "scan_shape",
                Q(
                    profile__in=tuple(UsageProfile), purpose__in=tuple(ScanPurpose), generation__gte=1,
                    requested_start__lt=F("requested_end"), requested_end__lte=F("started_at"),
                )
                & _pair("policy_epoch", "policy_digest")
                & (
                    Q(state=ScanState.PARTIAL, terminal_page_seen=False)
                    & _all_null("finished_at", "failure_code", "replacement_not_before")
                    | Q(
                        state=ScanState.COMPLETE, terminal_page_seen=True, finished_at__gte=F("started_at"),
                        finished_at__isnull=False, failure_code__isnull=True, replacement_not_before__isnull=True,
                    )
                    | Q(
                        state=ScanState.FAILED, terminal_page_seen=False, finished_at__gte=F("started_at"),
                        replacement_not_before__gte=F("finished_at"), failure_code__in=tuple(UsageFailureCode),
                    ) & _all_set("finished_at", "failure_code", "replacement_not_before")
                ),
            ),
        ]
        indexes = [_index("scan_scope_state", "scope", "state"), _index("scan_scope_profile_gen", "scope", "profile", "generation")]


class ScopeUsageHealth(_MutableObservation):
    scope = _one(UsageScope)
    revision = models.PositiveBigIntegerField(default=1)
    state = _enum(UsageHealthState, default=UsageHealthState.UNRESOLVED)
    reason = _enum(HealthReason, nullable=True, default=HealthReason.COVERAGE_MISSING)
    facts_revision = models.PositiveBigIntegerField(default=1)
    applied_facts_revision = models.PositiveBigIntegerField(null=True)
    policy_epoch = _fk(_EPOCH, nullable=True)
    policy_digest = _digest()
    complete_scan = _fk(UsageScan, nullable=True, related_name="+")
    window_start = _date()
    window_end = _date()
    scan_started_at = _date()
    valid_until = _date()
    observed_total = models.DecimalField(max_digits=58, decimal_places=18, null=True)
    unquantifiable_count = models.PositiveBigIntegerField(default=0)
    conflict_count = models.PositiveBigIntegerField(default=0)
    selected_generation = models.PositiveBigIntegerField(null=True)
    selected_window_end = _date()
    clear_min_generation = models.PositiveBigIntegerField(default=0)
    clear_min_window_end = _date()

    class Meta:
        constraints = [
            _check(
                "scope_health_shape",
                Q(revision__gte=1, facts_revision__gte=1) & _health_shape()
                & _pair("selected_generation", "selected_window_end", "complete_scan", "window_start",
                        "window_end", "scan_started_at", "valid_until", "observed_total", "policy_epoch", "policy_digest")
                & (Q(selected_generation__isnull=True) | Q(
                    selected_generation__gte=1, selected_window_end=F("window_end"),
                    window_start__lt=F("window_end"), observed_total__gte=0,
                ))
                & (
                    Q(clear_min_generation=0, clear_min_window_end__isnull=True)
                    | Q(clear_min_generation__gte=1, clear_min_window_end__isnull=False)
                )
                & (
                    ~Q(state=UsageHealthState.CURRENT)
                    | (
                        _all_set("complete_scan", "applied_facts_revision")
                        & Q(
                            applied_facts_revision=F("facts_revision"), unquantifiable_count=0,
                            conflict_count=0, selected_generation__gte=F("clear_min_generation"),
                        )
                        & (Q(clear_min_window_end__isnull=True) | Q(selected_window_end__gte=F("clear_min_window_end")))
                    )
                ),
            ),
        ]


class UsageScanRequirement(_ObservationRow):
    scan = _fk(UsageScan)
    org = _fk(_ORG, nullable=True)
    kind = _enum(("INITIAL", "CURRENT", "OPEN", "HEALTH", "HISTORY"))
    required_start = models.DateTimeField()
    required_end = models.DateTimeField()
    mapping = _uuid()

    class Meta:
        constraints = [
            _uniq("scan_requirement", "scan", "kind", "org", "mapping", "required_start", "required_end",
                  nulls_distinct=False),
            _check(
                "scan_requirement_shape",
                Q(required_start__lt=F("required_end"))
                & (
                    Q(kind__in=("HEALTH", "HISTORY")) & _all_null("org", "mapping")
                    | Q(kind="INITIAL") & _all_set("org", "mapping")
                    | Q(kind__in=("CURRENT", "OPEN"), org__isnull=False)
                ),
            ),
        ]
        indexes = [_index("requirement_org_bounds", "org", "required_start", "required_end")]


class UsagePageClaim(_MutableObservation):
    scan = _fk(UsageScan)
    ordinal = models.PositiveBigIntegerField()
    requested_cursor = _text(4096, nullable=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    lease_id = _uuid()
    lease_until = _date()
    lane_fence = models.PositiveBigIntegerField(null=True)
    dispatched_at = _date()
    completed_at = _date()
    state = _enum(("PENDING", "READING", "APPLIED", "FAILED"), default="PENDING")
    response_digest = _digest()
    next_cursor = _text(4096, nullable=True)
    terminal = models.BooleanField(default=False)
    last_error = _enum(UsageFailureCode, nullable=True)
    first_failure_at = _date()
    retry_at = _date()
    first_receipt_at = _date()
    oa_bucket_starts = models.JSONField(default=list)

    class Meta:
        constraints = [
            _uniq("claim_ordinal", "scan", "ordinal"),
            _check(
                "claim_shape",
                Q(attempts__lte=3)
                & (
                    Q(state="READING", retry_at__isnull=True, attempts__gte=1)
                    & _all_set("lease_id", "lease_until", "lane_fence", "dispatched_at")
                    | Q(state="PENDING", terminal=False, attempts__lte=2)
                    & _all_null("lease_id", "lease_until", "lane_fence", "completed_at", "response_digest")
                    | Q(state="APPLIED", attempts__gte=1)
                    & _all_set("completed_at", "first_receipt_at", "response_digest")
                    & _all_null("lease_id", "lease_until", "lane_fence", "retry_at")
                    & (Q(terminal=True, next_cursor__isnull=True) | Q(terminal=False, next_cursor__isnull=False))
                    | Q(state="FAILED", attempts=3, terminal=False, last_error__in=tuple(UsageFailureCode))
                    & _all_set("last_error", "first_failure_at")
                    & _all_null("lease_id", "lease_until", "lane_fence", "retry_at")
                ),
            ),
        ]
        indexes = [_index("claim_scan_retry", "scan", "state", "retry_at")]


class UsageObservedInterval(_ObservationRow):
    scan = _one(UsageScan)
    scope = _fk(UsageScope)
    start = models.DateTimeField()
    end = models.DateTimeField()
    scan_started_at = models.DateTimeField()
    scan_finished_at = models.DateTimeField()
    profile = _enum(UsageProfile)

    class Meta:
        constraints = [
            _check("observed_bounds", Q(
                start__lt=F("end"), end__lte=F("scan_started_at"), scan_started_at__lte=F("scan_finished_at"),
                profile__in=tuple(UsageProfile),
            )),
        ]
        indexes = [_index("observed_scope_bounds", "scope", "profile", "start", "end")]


class ProviderUsageRecord(_MutableObservation):
    scope = _fk(UsageScope)
    kind = _enum(("DG_REQUEST", "OA_BUCKET"))
    identity_key = _text(64)
    provider = _enum((_DG, _OA))
    natural_identity = models.JSONField()
    first_seen_at = models.DateTimeField()
    event_at = models.DateTimeField()
    retention_at = models.DateTimeField()
    mapping = _fk(_MAPPING, nullable=True)
    attribution = _enum(Attribution)
    current_version = _fk("ProviderUsageVersion", nullable=True, related_name="+")
    accepted_generation = models.PositiveBigIntegerField(default=0)
    issue = _enum(ObservationIssue, nullable=True)
    placed_week = _fk(UsageWeek, nullable=True)
    returned_project_id = _text(nullable=True)
    returned_api_key_id = _text(nullable=True)
    request_id = _text(nullable=True)

    class Meta:
        constraints = [
            _uniq("record_identity", "provider", "kind", "identity_key"),
            _uniq("record_request", "provider", "request_id", condition=Q(request_id__isnull=False)),
            _check(
                "record_shape",
                Q(attribution__in=tuple(Attribution), retention_at__gte=F("event_at"))
                & (Q(issue__isnull=True) | Q(issue__in=tuple(ObservationIssue)))
                & (
                    Q(kind="DG_REQUEST", provider=_DG, request_id__isnull=False, retention_at=F("event_at"))
                    | Q(kind="OA_BUCKET", provider=_OA, request_id__isnull=True, placed_week__isnull=True)
                )
                & (
                    ~Q(attribution__in=(Attribution.EXACT_KEY, Attribution.PROJECT_ONLY))
                    | Q(mapping__isnull=False)
                ),
            ),
        ]
        indexes = [
            _index("record_mapping_event", "mapping", "event_at"),
            _index("record_scope_attr", "scope", "attribution", "id"),
            _index("record_retention", "retention_at", "id"),
        ]


_OA_METRICS = (
    "input_tokens", "output_tokens", "input_cached_tokens", "input_audio_tokens",
    "input_cached_audio_tokens", "output_audio_tokens", "num_model_requests",
)


class ProviderUsageVersion(_ObservationRow):
    record = _fk(ProviderUsageRecord)
    revision = models.PositiveBigIntegerField()
    normalized_digest = _text(64)
    normalization_version = models.PositiveSmallIntegerField(default=1)
    safe_facts = models.JSONField()
    source_scan = _fk(UsageScan, nullable=True)
    source_page = _fk(UsagePageClaim, nullable=True)
    source_generation = models.PositiveBigIntegerField()
    first_receipt_at = models.DateTimeField()
    source_scope = _fk(UsageScope)
    source_interval_start = models.DateTimeField()
    source_interval_end = models.DateTimeField()
    source_scan_started_at = models.DateTimeField()
    completion = _enum(DGCompletion, nullable=True)
    completed_at = _date()
    duration_seconds = models.DecimalField(max_digits=38, decimal_places=18, null=True)
    response_code = models.PositiveSmallIntegerField(null=True)
    input_tokens = models.PositiveBigIntegerField(null=True)
    output_tokens = models.PositiveBigIntegerField(null=True)
    input_cached_tokens = models.PositiveBigIntegerField(null=True)
    input_audio_tokens = models.PositiveBigIntegerField(null=True)
    input_cached_audio_tokens = models.PositiveBigIntegerField(null=True)
    output_audio_tokens = models.PositiveBigIntegerField(null=True)
    num_model_requests = models.PositiveBigIntegerField(null=True)

    class Meta:
        constraints = [
            _uniq("version_revision", "record", "revision"),
            _uniq("version_digest", "record", "normalized_digest", "normalization_version"),
            _check(
                "version_shape",
                Q(revision__gte=1, source_generation__gte=1, normalization_version=1,
                  source_interval_start__lt=F("source_interval_end"),
                  source_interval_end__lte=F("source_scan_started_at"))
                & (
                    _all_null("completion", "completed_at", "duration_seconds", "response_code")
                    | _all_null(*_OA_METRICS)
                    & (
                        Q(completion=DGCompletion.COMPLETE, completed_at__isnull=False)
                        | Q(completion=DGCompletion.COMPLETION_UNKNOWN, completed_at__isnull=True)
                    ) & _all_set("completion")
                )
                & (Q(duration_seconds__isnull=True) | Q(duration_seconds__gte=0))
                & (Q(response_code__isnull=True) | Q(response_code__range=(100, 599)))
                & (
                    Q(input_cached_tokens__isnull=True) | Q(input_tokens__isnull=True)
                    | Q(input_cached_tokens__lte=F("input_tokens"))
                )
                & (
                    Q(input_cached_audio_tokens__isnull=True) | Q(input_audio_tokens__isnull=True)
                    | Q(input_cached_audio_tokens__lte=F("input_audio_tokens"))
                ),
            ),
        ]
        indexes = [_index("version_received", "first_receipt_at", "id")]


class UsageCoverageGap(_MutableObservation):
    scope = _fk(UsageScope)
    org = _fk(_ORG, nullable=True)
    record = _fk(ProviderUsageRecord, nullable=True)
    start = _date()
    end = _date()
    reason = _enum(UsageFailureCode)
    state = _enum(("OPEN", "RESOLVED"), default="OPEN")
    first_seen_at = models.DateTimeField()
    resolved_at = _date()
    last_scan = _fk(UsageScan, nullable=True)
    gap_key = _text(64, unique=True)

    class Meta:
        constraints = [
            _check("gap_shape",
                   (Q(state="OPEN", resolved_at__isnull=True) | Q(state="RESOLVED", resolved_at__isnull=False))
                   & (Q(record__isnull=False) | _all_set("start", "end") & Q(start__lt=F("end")))),
        ]
        indexes = [_index("gap_org_state", "org", "state"), _index("gap_scope_state", "scope", "state")]


class UsageOrgState(_MutableObservation):
    org = _one(_ORG, primary_key=True)
    dirty_revision = models.PositiveBigIntegerField(default=1)
    applied_revision = models.PositiveBigIntegerField(default=0)
    next_due_at = models.DateTimeField()
    last_completed_at = _date()
    dirty_after_record_id = models.PositiveBigIntegerField(null=True)

    class Meta:
        constraints = [_check("org_revision", Q(dirty_revision__gte=1, applied_revision__lte=F("dirty_revision")))]


class UsageWeekProjection(_ObservationRow):
    week = _one(UsageWeek)
    source = _enum(("LIVE_CURRENT_PROJECTION",), default="LIVE_CURRENT_PROJECTION")
    reconciled_at = models.DateTimeField()
    selected_plan_id = models.PositiveBigIntegerField()
    selected_rank = models.PositiveIntegerField()
    catalogue_revision = models.PositiveBigIntegerField()
    selected_timezone = _text(64)
    opening_stt_seconds_limit = models.PositiveBigIntegerField()
    opening_notes_limit = models.PositiveBigIntegerField()
    predecessor_week = _fk(UsageWeek, nullable=True, related_name="+")
    successor_week = _fk(UsageWeek, nullable=True, related_name="+")


class UsageReconcileAudit(_ObservationRow):
    org = _fk(_ORG)
    dirty_revision = models.PositiveBigIntegerField()
    action = _enum(("OVERRUN_RECORDED", "OVERRUN_WRITTEN_OFF", "MINT_UNKNOWN"))
    subject = _text()
    source_week = _fk(UsageWeek, nullable=True, related_name="+")
    successor_week = _fk(UsageWeek, nullable=True, related_name="+")
    units = models.PositiveBigIntegerField(null=True)
    event_at = models.DateTimeField()
    audit_event = models.ForeignKey("selahcue_audit.AuditEvent", null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [_uniq("reconcile_audit", "org", "dirty_revision", "action", "subject")]


class SttScopeReadiness(_MutableObservation):
    scope = _one(UsageScope)
    revision = models.PositiveBigIntegerField(default=1)
    latest_complete_scan = _fk(UsageScan, nullable=True)
    scan_started_at = _date()
    scan_finished_at = _date()
    observed_through = _date()
    valid_until = _date()
    unattributed_blocked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            _check("stt_scope_shape", Q(revision__gte=1) & _pair(
                "latest_complete_scan", "scan_started_at", "scan_finished_at", "observed_through", "valid_until",
            )),
        ]


class SttOrgReadiness(_MutableObservation):
    org = _one(_ORG, primary_key=True)
    publication_revision = models.PositiveBigIntegerField(default=1)
    mapping = models.UUIDField()
    published_at = models.DateTimeField()
    observed_through = models.DateTimeField()
    valid_until = models.DateTimeField()
    placement_gap = models.BooleanField(default=False)
    health = _fk(_HEALTH)
    health_revision = models.PositiveBigIntegerField()
    org_dirty_revision = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            _check("stt_org_shape", Q(
                publication_revision__gte=1, health_revision__gte=1, org_dirty_revision__gte=1,
                health=_DG, published_at__lt=F("valid_until"), observed_through__lte=F("published_at"),
            )),
        ]


class SttOrgReadinessScope(_ObservationRow):
    publication = _fk(SttOrgReadiness)
    scope = _fk(SttScopeReadiness)
    scope_revision = models.PositiveBigIntegerField()
    coverage_valid_until = models.DateTimeField()
    observed_through = models.DateTimeField()

    class Meta:
        constraints = [
            _uniq("publication_scope", "publication", "scope"),
            _check("publication_scope_rev", Q(scope_revision__gte=1)),
        ]


class SttOrgCoverage(_ObservationRow):
    publication = _fk(SttOrgReadiness)
    observed_interval = _fk(UsageObservedInterval)
    required_start = models.DateTimeField()
    required_end = models.DateTimeField()

    class Meta:
        constraints = [
            _uniq("publication_fragment", "publication", "observed_interval", "required_start", "required_end"),
            _check("publication_bounds", Q(required_start__lt=F("required_end"))),
        ]


class UsageWork(_UuidObservation):
    kind = _enum(("SCAN", "RECONCILE", "ATTRIBUTE", "MINT_RECOVERY", "RETENTION"))
    scope = _fk(UsageScope, nullable=True)
    scan = _fk(UsageScan, nullable=True)
    org = _fk(_ORG, nullable=True)
    attempt_id = _uuid()
    retention_kind = _enum(RetentionKind, nullable=True)
    subject_key = _text()
    state = _enum(("PENDING", "RUNNING", "COMPLETE", "FAILED"), default="PENDING")
    execution_generation = models.PositiveBigIntegerField(default=1)
    due_at = models.DateTimeField()
    lease_id = _uuid()
    lease_until = _date()
    started_at = _date()
    finished_at = _date()
    last_error = _enum(UsageFailureCode, nullable=True)

    class Meta:
        constraints = [
            _uniq("work_live_subject", "kind", "subject_key", condition=Q(state__in=("PENDING", "RUNNING"))),
            _check(
                "work_shape",
                Q(execution_generation__gte=1)
                & (
                    Q(kind="SCAN") & _all_set("scope", "scan") & _all_null("org", "attempt_id", "retention_kind")
                    | Q(kind="RECONCILE", org__isnull=False) & _all_null("scope", "scan", "attempt_id", "retention_kind")
                    | Q(kind="ATTRIBUTE", scope__isnull=False) & _all_null("scan", "org", "attempt_id", "retention_kind")
                    | Q(kind="MINT_RECOVERY", attempt_id__isnull=False) & _all_null("scope", "scan", "org", "retention_kind")
                    | Q(kind="RETENTION", retention_kind__in=tuple(RetentionKind)) & _all_set("retention_kind")
                    & _all_null("scope", "scan", "org", "attempt_id")
                )
                & (
                    Q(state="RUNNING", finished_at__isnull=True) & _all_set("lease_id", "lease_until", "started_at")
                    | Q(state="PENDING", finished_at__isnull=True) & _all_null("lease_id", "lease_until")
                    | Q(state__in=("COMPLETE", "FAILED"), finished_at__isnull=False) & _all_null("lease_id", "lease_until")
                ),
            ),
        ]
        indexes = [_index("work_due", "state", "due_at")]


class UsageOutbox(_UuidObservation):
    work = _fk(UsageWork)
    generation = models.PositiveBigIntegerField()
    state = _enum(("PENDING", "PUBLISHING", "SENT", "ACKED", "FAILED", "CANCELLED"), default="PENDING")
    publish_attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    lease_id = _uuid()
    lease_until = _date()
    sent_at = _date()
    acked_at = _date()
    last_error = _enum(UsageFailureCode, nullable=True)
    first_failure_at = _date()

    class Meta:
        constraints = [
            _uniq("outbox_generation", "work", "generation"),
            _uniq("outbox_outstanding", "work", condition=Q(state__in=("PENDING", "PUBLISHING", "SENT"))),
            _check(
                "outbox_shape",
                Q(generation__gte=1, publish_attempts__lte=3)
                & (
                    Q(state="PUBLISHING", publish_attempts__gte=1) & _all_set("lease_id", "lease_until")
                    | Q(state__in=("PENDING", "SENT", "ACKED", "FAILED", "CANCELLED")) & _all_null("lease_id", "lease_until")
                )
                & (~Q(state="SENT") | Q(sent_at__isnull=False))
                & (~Q(state="ACKED") | Q(acked_at__isnull=False)),
            ),
        ]
        indexes = [_index("outbox_due", "state", "available_at")]


class UsageDiscoveryCursor(_MutableObservation):
    purpose = _enum(("INITIAL_MAPPING", "RECENT_SCOPE", "HISTORY_SCOPE", "RECOVERY", "RETENTION"))
    last_id = models.PositiveBigIntegerField(null=True)
    last_uuid = _uuid()
    last_at = _date()

    class Meta:
        constraints = [_uniq("discovery_purpose", "purpose")]


class UsageRetentionCursor(_MutableObservation):
    kind = _enum(RetentionKind)
    cutoff_at = models.DateTimeField()
    after_id = models.PositiveBigIntegerField(null=True)
    after_uuid = _uuid()
    cycle_started_at = models.DateTimeField()

    class Meta:
        constraints = [_uniq("retention_kind", "kind")]
