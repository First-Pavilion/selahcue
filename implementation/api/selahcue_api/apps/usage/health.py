"""Observed provider health production and one-statement consumer projections."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.db import connection
from django.db.models import DecimalField, F, Q, Sum
from django.db.models.functions import Cast
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.graphql.context import ActorContext, ActorKind
from selahcue_api.apps.providers.configuration import get_provider_configuration
from selahcue_api.apps.providers.contracts import ProviderConfigurationError, ProviderKind, ProviderScope
from selahcue_api.apps.providers.models import ProviderCapacityPool
from selahcue_api.apps.providers.policy_publication import canonical_scope, digest

from .models import ProviderUsageHealthState, ProviderUsageRecord, ScopeUsageHealth, UsageScope
from .observation_contracts import (
    Attribution, HealthReason, ProviderUsageHealth, UsageFailureCode as Code, UsageHealthState as State,
    UsageRejected,
)

FRESHNESS = timedelta(seconds=300)
HEALTH_WINDOW = timedelta(hours=24)
_NUMERIC = DecimalField(max_digits=58, decimal_places=18)

# Every reader inserts this CTE into its single parameterized statement. Check the
# persisted current epoch through the entire enrolled ∪ published parent set.
HEALTH_SQL = """
WITH input(provider, checked_at) AS (VALUES (%s, %s)),
required(parent) AS (
    SELECT parent_scope_id FROM selahcue_usage_usagescope JOIN input USING (provider)
    UNION
    SELECT parent_scope_id FROM selahcue_providers_providercapacitypool JOIN input USING (provider)
),
scope_inputs AS (
    SELECT req.parent, h.valid_until,
        CASE
          WHEN s.id IS NULL OR pool.id IS NULL THEN 'SCOPE_MISSING'
          WHEN h.id IS NULL OR h.complete_scan_id IS NULL THEN
            CASE WHEN pool.current_epoch_id IS NULL THEN 'POLICY_MISMATCH'
                 ELSE COALESCE(h.reason, 'COVERAGE_MISSING') END
          WHEN epoch.id IS NULL OR h.policy_epoch_id <> epoch.id
               OR h.policy_digest <> epoch.digest THEN 'POLICY_MISMATCH'
          WHEN h.state = 'BLOCKED' THEN 'THRESHOLD'
          WHEN h.state <> 'CURRENT' THEN h.reason
          WHEN h.facts_revision <> h.applied_facts_revision
               OR h.selected_generation < h.clear_min_generation
               OR h.selected_window_end < h.clear_min_window_end
               OR h.selected_generation <> scan.generation
               OR h.selected_window_end <> scan.requested_end
               OR scan.state <> 'COMPLETE' OR scan.policy_epoch_id <> epoch.id
               OR scan.policy_digest <> epoch.digest
               OR h.scan_started_at <> scan.started_at
               THEN 'COVERAGE_MISSING'
          WHEN h.valid_until IS NULL OR h.valid_until <= input.checked_at THEN 'COVERAGE_STALE'
        END AS reason
    FROM required req CROSS JOIN input
    LEFT JOIN selahcue_usage_usagescope s
      ON s.provider = input.provider AND s.parent_scope_id = req.parent
    LEFT JOIN selahcue_providers_providercapacitypool pool
      ON pool.provider = input.provider AND pool.parent_scope_id = req.parent AND pool.id = s.pool_id
    LEFT JOIN selahcue_providers_scopepolicyepoch epoch
      ON epoch.id = pool.current_epoch_id AND epoch.pool_id = pool.id
    LEFT JOIN selahcue_usage_scopeusagehealth h ON h.scope_id = s.id
    LEFT JOIN selahcue_usage_usagescan scan ON scan.id = h.complete_scan_id AND scan.scope_id = s.id
),
health_projection AS (
    SELECT ph.revision, MIN(scope_inputs.valid_until) AS valid_until,
      CASE
        WHEN ph.provider IS NULL THEN 'COVERAGE_MISSING'
        WHEN COUNT(CASE WHEN scope_inputs.reason = 'THRESHOLD' THEN 1 END) > 0 THEN 'THRESHOLD'
        WHEN COUNT(CASE WHEN scope_inputs.reason = 'POLICY_MISMATCH' THEN 1 END) > 0 THEN 'POLICY_MISMATCH'
        WHEN COUNT(CASE WHEN scope_inputs.reason = 'SCOPE_MISSING' THEN 1 END) > 0 THEN 'SCOPE_MISSING'
        WHEN COUNT(CASE WHEN scope_inputs.reason = 'IDENTITY_CONFLICT' THEN 1 END) > 0 THEN 'IDENTITY_CONFLICT'
        WHEN COUNT(CASE WHEN scope_inputs.reason = 'UNQUANTIFIABLE' THEN 1 END) > 0 THEN 'UNQUANTIFIABLE'
        WHEN COUNT(CASE WHEN scope_inputs.reason = 'COVERAGE_MISSING' THEN 1 END) > 0
             OR COUNT(scope_inputs.parent) = 0 THEN 'COVERAGE_MISSING'
        WHEN COUNT(CASE WHEN scope_inputs.reason = 'COVERAGE_STALE' THEN 1 END) > 0 THEN 'COVERAGE_STALE'
      END AS reason
    FROM input LEFT JOIN selahcue_usage_providerusagehealthstate ph USING (provider)
    LEFT JOIN scope_inputs ON 1=1 GROUP BY ph.provider, ph.revision
)
"""


def utc_parameter(at):
    if not isinstance(at, datetime) or at.utcoffset() != timedelta(0):
        raise ValueError("Expected an aware UTC check time")
    return connection.ops.adapt_datetimefield_value(at)


def result_time(value):
    if isinstance(value, str):  # raw SQLite aggregate results have no Django converters
        value = datetime.fromisoformat(value)
    if value is not None and timezone.is_naive(value):
        return timezone.make_aware(value, timezone=UTC)
    return value


def read_provider_usage_health(provider: ProviderKind, at: datetime) -> ProviderUsageHealth:
    if type(provider) is not str or provider not in ("deepgram", "openai"):
        raise ValueError("Invalid usage provider")
    with connection.cursor() as cursor:
        cursor.execute(HEALTH_SQL + "SELECT revision, valid_until, reason FROM health_projection",
                       [provider, utc_parameter(at)])
        revision, valid_until, reason = cursor.fetchone()
    reason = None if reason is None else HealthReason(reason)
    state = State.CURRENT if reason is None else State.BLOCKED if reason == HealthReason.THRESHOLD else State.UNRESOLVED
    return ProviderUsageHealth(provider, state, at, revision, result_time(valid_until), reason)


def lock_provider(provider, now):
    row, _ = ProviderUsageHealthState.objects.select_for_update().get_or_create(
        provider=provider, defaults={"created_at": now, "updated_at": now},
    )
    return row


def lock_scope(provider, scope_id):
    return UsageScope.objects.select_for_update().get(pk=scope_id, provider=provider)


def producer_policy(scope):
    try:
        config = get_provider_configuration(required_role="usage")
    except ProviderConfigurationError:
        raise UsageRejected(Code.CONFIG_UNAVAILABLE) from None
    identity = ProviderScope(scope.provider, scope.parent_scope_id)
    epoch = ProviderCapacityPool.objects.filter(
        pk=scope.pool_id, provider=scope.provider, parent_scope_id=scope.parent_scope_id,
    ).select_related("current_epoch").first()
    if epoch is None or epoch.current_epoch is None:
        raise UsageRejected(Code.SCOPE_MISSING)
    local = None if config.policy is None else next((p for p in config.policy.scopes if p.scope == identity), None)
    if local is None or sum(c.scope == identity for c in config.usage_credentials) != 1:
        raise UsageRejected(Code.SCOPE_MISSING)
    if digest(canonical_scope(local)) != epoch.current_epoch.digest:
        raise UsageRejected(Code.POLICY_MISMATCH)
    return epoch.current_epoch, local


def scope_health(scope, now):
    return ScopeUsageHealth.objects.select_for_update().get_or_create(
        scope=scope, defaults={"created_at": now, "updated_at": now},
    )[0]


def operational_audit(action, target, identifier, *, request_id, reason="", after=None):
    record_audit_event(
        ActorContext(kind=ActorKind.SERVICE, actor_id="provider-usage"),
        action=action, target_type=target, target_id=str(identifier), reason=reason,
        after=after, request_id=str(request_id), source_surface="provider_usage",
    )


def update_provider(row, now):
    health = read_provider_usage_health(row.provider, now)
    changed = (row.state, row.reason) != (health.status, health.reason)
    row.revision += 1
    row.updated_at = now
    row.state, row.reason = health.status, health.reason
    row.save(update_fields=("revision", "updated_at", "state", "reason"))
    if changed:
        operational_audit(
            "usage.health_changed", "ProviderUsageHealthState", row.provider,
            request_id=f"{row.provider}-{row.revision}", reason=row.reason or "",
            after={"revision": row.revision, "state": row.state},
        )


def producer_failure(row, evaluation, code, now):
    reasons = {
        Code.SCOPE_MISSING: HealthReason.SCOPE_MISSING,
        Code.CONFIG_UNAVAILABLE: HealthReason.COVERAGE_MISSING,
        Code.POLICY_MISMATCH: HealthReason.POLICY_MISMATCH,
    }
    if evaluation.state != State.BLOCKED and evaluation.reason != reasons[code]:
        evaluation.state, evaluation.reason = State.UNRESOLVED, reasons[code]
        evaluation.revision += 1
        evaluation.updated_at = now
        evaluation.save(update_fields=("state", "reason", "revision", "updated_at"))
        update_provider(row, now)


def invalidate(row, evaluation, generation, window_end, now):
    evaluation.facts_revision += 1
    evaluation.revision += 1
    evaluation.updated_at = now
    evaluation.clear_min_generation = max(
        evaluation.clear_min_generation, evaluation.selected_generation or 0, generation,
    )
    evaluation.clear_min_window_end = max(
        value for value in (evaluation.clear_min_window_end, evaluation.selected_window_end, window_end)
        if value is not None
    )
    if evaluation.state != State.BLOCKED:
        evaluation.state, evaluation.reason = State.UNRESOLVED, HealthReason.COVERAGE_MISSING
    evaluation.save(update_fields=(
        "facts_revision", "revision", "updated_at", "clear_min_generation", "clear_min_window_end", "state", "reason",
    ))
    update_provider(row, now)


def _population(scope, start, end):
    records = ProviderUsageRecord.objects.filter(scope=scope, event_at__gte=start, event_at__lt=end)
    conflicts = records.filter(attribution=Attribution.DISCREPANCY).count()
    unattributed = records.filter(attribution=Attribution.UNATTRIBUTED)
    if scope.provider == "deepgram":
        unknown = Q(current_version__duration_seconds__isnull=True)
        amount = F("current_version__duration_seconds")
    else:
        unknown = Q(current_version__input_tokens__isnull=True) | Q(current_version__output_tokens__isnull=True)
        amount = Cast("current_version__input_tokens", _NUMERIC) + Cast("current_version__output_tokens", _NUMERIC)
    if connection.vendor == "sqlite":
        # SQLite has no exact numeric SUM. Retain the same integer-scaled arithmetic
        # for the lightweight local service tests, without claiming row-lock parity.
        values = unattributed.exclude(unknown)
        if scope.provider == "deepgram":
            terms = (to_attoseconds(item) for item in values.values_list("current_version__duration_seconds", flat=True))
        else:
            terms = ((i + o) * 10**18 for i, o in values.values_list(
                "current_version__input_tokens", "current_version__output_tokens",
            ))
        scaled = sum(terms)
        total = Decimal((0, tuple(int(d) for d in str(scaled)), -18))
    else:
        total = unattributed.aggregate(total=Sum(amount, output_field=_NUMERIC))["total"] or Decimal(0)
    return total, unattributed.filter(unknown).count(), conflicts


def to_attoseconds(value):
    _, digits, exponent = value.as_tuple()
    coefficient = int("".join(map(str, digits)))
    power = 18 + exponent
    return coefficient * 10**power if power >= 0 else coefficient // 10**(-power)


def publish_evaluation(provider, scope, evaluation, scan, threshold, now):
    end = scan.requested_end
    if (
        scan.requested_start > end - HEALTH_WINDOW
        or scan.generation < max(evaluation.selected_generation or 0, evaluation.clear_min_generation)
        or any(end < bound for bound in (evaluation.selected_window_end, evaluation.clear_min_window_end) if bound)
        or evaluation.complete_scan_id == scan.pk
    ):
        return
    start, expiry = end - HEALTH_WINDOW, scan.started_at + FRESHNESS
    total, unknown, conflicts = _population(scope, start, end)
    if total > threshold:
        state, reason = State.BLOCKED, HealthReason.THRESHOLD
    elif conflicts:
        state, reason = State.UNRESOLVED, HealthReason.IDENTITY_CONFLICT
    elif unknown:
        state, reason = State.UNRESOLVED, HealthReason.UNQUANTIFIABLE
    elif now >= expiry:
        return
    else:
        state, reason = State.CURRENT, None
    if evaluation.state == State.BLOCKED and state == State.UNRESOLVED:
        return
    evaluation.state, evaluation.reason = state, reason
    evaluation.complete_scan = scan
    evaluation.selected_generation = scan.generation
    evaluation.selected_window_end = evaluation.window_end = end
    evaluation.window_start, evaluation.scan_started_at, evaluation.valid_until = start, scan.started_at, expiry
    evaluation.policy_epoch_id, evaluation.policy_digest = scan.policy_epoch_id, scan.policy_digest
    evaluation.observed_total, evaluation.unquantifiable_count, evaluation.conflict_count = total, unknown, conflicts
    evaluation.applied_facts_revision = evaluation.facts_revision
    evaluation.revision += 1
    evaluation.updated_at = now
    evaluation.save()
    update_provider(provider, now)
