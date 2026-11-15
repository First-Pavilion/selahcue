"""Immutable metadata identity and ordered replacement of provider facts."""
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import time

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from selahcue_api.apps.providers.configuration import get_provider_configuration
from selahcue_api.apps.providers.contracts import ProviderConfigurationError, ProviderScope
from selahcue_api.apps.providers.models import ProviderCredential

from . import health
from .contracts import UTCInterval
from .models import (
    ProviderUsageRecord, ProviderUsageVersion, SttScopeReadiness, UsageCoverageGap, UsageOrgState,
    UsagePageClaim, UsageScan, UsageScope, UsageWork,
)
from .observation_contracts import (
    Attribution, AttributionBatchResult, DGCompletion, DeepgramRequestObservation, IngestResult,
    ObservationIssue, OpenAIUsageBucketObservation, ScanState, UsageClaim, UsageFailureCode as Code,
    UsagePage, UsageProfile, UsageRejected,
)

RETENTION_AGE = timedelta(weeks=104)


def _json_default(value):
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Decimal):
        text = format(value, "f")
        return (text.rstrip("0").rstrip(".") if "." in text else text) if value else "0"
    raise TypeError


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False, default=_json_default,
    )


def safe_digest(domain, value):
    return sha256((domain + "\0" + canonical(value)).encode("utf-8")).hexdigest()


def _normalized(record):
    return json.loads(canonical(asdict(record)))


def _identity(scope, record, facts):
    if isinstance(record, DeepgramRequestObservation):
        return (
            "DG_REQUEST", {"provider": scope.provider, "request_id": record.request_id},
            {key: facts[key] for key in ("request_id", "project_id", "api_key_id", "created_at")},
            record.created_at, record.created_at, record.project_id, record.api_key_id, record.request_id,
        )
    dimensions = record.dimensions
    natural = {
        "provider": scope.provider, "parent_scope_id": scope.parent_scope_id,
        "start": facts["start"], "end": facts["end"], "dimensions": facts["dimensions"],
        "profile": UsageProfile.OA_COMPLETIONS_1H_V1,
    }
    return (
        "OA_BUCKET", natural, natural, record.start, record.end, dimensions.project_id, dimensions.api_key_id, None,
    )


def _attribute(scope, project, key):
    if project is None:
        return None, Attribution.UNATTRIBUTED
    mappings = ProviderCredential.objects.filter(provider=scope.provider, external_project_id=project)
    if scope.provider == "deepgram":
        if key is None:
            return None, Attribution.UNATTRIBUTED
        mapping = mappings.filter(external_api_key_id=key).first()
        if mapping is None:
            return None, Attribution.UNATTRIBUTED
        if mapping.parent_scope_id != scope.parent_scope_id:
            return None, Attribution.DISCREPANCY
        return mapping, Attribution.EXACT_KEY
    mapping = mappings.first()
    if mapping is None:
        return None, Attribution.UNATTRIBUTED
    if mapping.parent_scope_id != scope.parent_scope_id:
        return None, Attribution.DISCREPANCY
    if key is None:
        return mapping, Attribution.PROJECT_ONLY
    if key != mapping.external_api_key_id:
        return None, Attribution.DISCREPANCY
    return mapping, Attribution.EXACT_KEY


def set_gap(scope, code, now, *, record=None, org_id=None, start=None, end=None, scan=None):
    key = safe_digest("usage-gap-v1", (scope.pk, code, record.pk if record else None, org_id, start, end))
    gap, created = UsageCoverageGap.objects.get_or_create(
        gap_key=key,
        defaults={
            "scope": scope, "org_id": org_id, "record": record, "start": start, "end": end, "reason": code,
            "first_seen_at": now, "created_at": now, "updated_at": now, "last_scan": scan,
        },
    )
    if not created:
        want = (scope.pk, code, record.pk if record else None, org_id, start, end)
        if (gap.scope_id, gap.reason, gap.record_id, gap.org_id, gap.start, gap.end) != want:
            raise UsageRejected(Code.IDENTITY_CONFLICT)
        gap.last_scan = scan
        gap.updated_at = now
        gap.state, gap.resolved_at = "OPEN", None
        gap.save(update_fields=("last_scan", "updated_at", "state", "resolved_at"))
    return gap


def bump_scope(scope, now):
    scope.normalization_revision += 1
    scope.updated_at = now
    scope.save(update_fields=("normalization_revision", "updated_at"))
    if scope.provider != "deepgram":
        return None
    ready, _ = SttScopeReadiness.objects.select_for_update().get_or_create(
        scope=scope, defaults={"created_at": now, "updated_at": now},
    )
    ready.revision += 1
    ready.updated_at = now
    ready.save(update_fields=("revision", "updated_at"))
    return ready


def dirty_orgs(org_ids, now):
    from .usage_tasks import ensure_work

    for org_id in sorted(set(org_ids)):
        state, created = UsageOrgState.objects.select_for_update().get_or_create(
            org_id=org_id, defaults={"created_at": now, "updated_at": now, "next_due_at": now},
        )
        if not created:
            state.dirty_revision += 1
            state.next_due_at = state.updated_at = now
            state.save(update_fields=("dirty_revision", "next_due_at", "updated_at"))
        ensure_work("RECONCILE", str(org_id), now, org_id=org_id)


def _health_identity(row, version):
    if row.attribution == Attribution.UNATTRIBUTED:
        if row.provider == "deepgram":
            metric = version.duration_seconds if version is not None else None
        else:
            metric = (version.input_tokens, version.output_tokens) if version is not None else None
            if metric is not None and None in metric:
                metric = None
        return row.attribution, metric
    if row.attribution == Attribution.DISCREPANCY:
        return row.attribution, None
    return None


def _mark_conflict(row, scope, scan, now):
    was_conflict = row.issue == ObservationIssue.IDENTITY_CONFLICT
    row.attribution = Attribution.DISCREPANCY
    row.issue = ObservationIssue.IDENTITY_CONFLICT
    generation = scan.generation if scan.scope_id == scope.pk else scope.next_scan_generation - 1
    row.conflict_generation = max(row.conflict_generation, row.accepted_generation, generation)
    row.updated_at = now
    row.save(update_fields=("attribution", "issue", "conflict_generation", "updated_at"))
    set_gap(scope, Code.IDENTITY_CONFLICT, now, record=row, org_id=row.mapping.org_id if row.mapping_id else None, scan=scan)
    if not was_conflict:
        health.operational_audit(
            "usage.identity_discrepancy", "ProviderUsageRecord", row.pk,
            request_id=f"{scan.pk}-{row.pk}", reason=Code.IDENTITY_CONFLICT,
            after={"scope_id": scope.pk, "scan_id": str(scan.pk), "generation": scan.generation},
        )


def _version(row, normalized, values, scan, claim, now):
    key = safe_digest("usage-normalization-v1", normalized)
    version = ProviderUsageVersion.objects.filter(record=row, normalized_digest=key, normalization_version=1).first()
    if version is not None:
        if version.safe_facts != normalized:
            raise UsageRejected(Code.IDENTITY_CONFLICT)
        return version
    revision = ProviderUsageVersion.objects.filter(record=row).aggregate(high=Max("revision"))["high"] or 0
    if isinstance(values, DeepgramRequestObservation):
        columns = {
            "completion": values.completion, "completed_at": values.completed_at,
            "duration_seconds": values.duration_seconds, "response_code": values.response_code,
        }
    else:
        columns = asdict(values.metrics)
    return ProviderUsageVersion.objects.create(
        record=row, revision=revision + 1, normalized_digest=key, safe_facts=normalized,
        created_at=now, source_scan=scan, source_page=claim, source_generation=scan.generation,
        first_receipt_at=now, source_scope_id=scan.scope_id, source_interval_start=scan.requested_start,
        source_interval_end=scan.requested_end, source_scan_started_at=scan.started_at, **columns,
    )


def _apply_fact(scope, scan, claim, observed, now):
    facts = _normalized(observed)
    kind, key_fields, natural, event, retention, project, key, request_id = _identity(scope, observed, facts)
    identity_key = safe_digest("usage-identity-v1", key_fields)
    row = ProviderUsageRecord.objects.select_for_update().filter(
        provider=scope.provider, kind=kind, identity_key=identity_key,
    ).first()
    initial = row is None
    if initial:
        mapping, attribution = _attribute(scope, project, key)
        row = ProviderUsageRecord.objects.create(
            scope=scope, kind=kind, provider=scope.provider, identity_key=identity_key, natural_identity=natural,
            first_seen_at=now, event_at=event, retention_at=retention, mapping=mapping, attribution=attribution,
            returned_project_id=project, returned_api_key_id=key, request_id=request_id,
            created_at=now, updated_at=now,
        )
    old_version = row.current_version if row.current_version_id else None
    prior_health = None if initial else _health_identity(row, old_version)
    prior_state = row.mapping_id, row.attribution, row.issue
    conflicting = (
        row.scope_id != scope.pk or row.event_at != event or row.request_id != request_id
        or (kind == "OA_BUCKET" and row.natural_identity != natural)
        or any(original is not None and incoming is not None and original != incoming
               for original, incoming in ((row.returned_project_id, project), (row.returned_api_key_id, key)))
    )
    same_generation_conflict = facts != old_version.safe_facts if old_version is not None else False
    if old_version is not None and kind == "DG_REQUEST":
        same_generation_conflict = any(
            value != old_version.safe_facts[field] for field, value in facts.items()
            if field not in ("project_id", "api_key_id")
        )
    if not initial and old_version is not None and scan.generation >= row.accepted_generation:
        conflicting |= (
            scan.generation == row.accepted_generation and same_generation_conflict
            or isinstance(observed, DeepgramRequestObservation)
            and (
                (old_version.completion == DGCompletion.COMPLETE and observed.completion != DGCompletion.COMPLETE)
                or (old_version.duration_seconds is not None and observed.duration_seconds is None)
            )
        )
    if conflicting:
        _mark_conflict(row, row.scope, scan, now)
        return row, "revised", prior_health != _health_identity(row, old_version)
    if not initial and (
        scan.generation < row.accepted_generation
        or row.issue == ObservationIssue.IDENTITY_CONFLICT and scan.generation <= row.conflict_generation
    ):
        return row, "duplicates", False

    row.returned_project_id = row.returned_project_id or project
    row.returned_api_key_id = row.returned_api_key_id or key
    mapping, attribution = _attribute(scope, row.returned_project_id, row.returned_api_key_id)
    if row.mapping_id is not None and (mapping is None or mapping.pk != row.mapping_id):
        _mark_conflict(row, scope, scan, now)
        return row, "revised", prior_health != _health_identity(row, old_version)
    row.mapping = mapping
    row.attribution = attribution
    if attribution == Attribution.DISCREPANCY:
        row.conflict_generation = max(row.conflict_generation, scan.generation)
        row.issue = ObservationIssue.IDENTITY_CONFLICT
    elif retention < row.first_seen_at - RETENTION_AGE:
        row.issue = ObservationIssue.ANCIENT_FACT
    elif row.issue != ObservationIssue.ANCIENT_FACT:
        if kind == "DG_REQUEST" and observed.completion == DGCompletion.COMPLETE and observed.duration_seconds is None:
            row.issue = ObservationIssue.METRIC_UNKNOWN
        elif row.issue != ObservationIssue.PLACEMENT_GAP:
            row.issue = None
    if kind == "DG_REQUEST":
        observed = replace(observed, project_id=row.returned_project_id, api_key_id=row.returned_api_key_id)
        facts = _normalized(observed)
    version = _version(row, facts, observed, scan, claim, now)
    row.current_version = version
    row.accepted_generation = scan.generation
    row.updated_at = now
    row.save(update_fields=(
        "returned_project_id", "returned_api_key_id", "mapping", "attribution", "issue", "current_version",
        "accepted_generation", "conflict_generation", "updated_at",
    ))
    issue_code = {
        ObservationIssue.ANCIENT_FACT: Code.PLACEMENT_GAP,
        ObservationIssue.METRIC_UNKNOWN: Code.METRIC_UNKNOWN,
        ObservationIssue.IDENTITY_CONFLICT: Code.IDENTITY_CONFLICT,
    }.get(row.issue)
    if issue_code is not None:
        set_gap(scope, issue_code, now, record=row, org_id=row.mapping.org_id if row.mapping_id else None, scan=scan)
    elif row.issue is None:
        UsageCoverageGap.objects.filter(record=row, state="OPEN", reason__in=(
            Code.IDENTITY_CONFLICT, Code.METRIC_UNKNOWN,
        )).update(state="RESOLVED", resolved_at=now, updated_at=now)
    unchanged = old_version is not None and version.pk == old_version.pk and prior_state == (
        row.mapping_id, row.attribution, row.issue,
    )
    outcome = "inserted" if initial else "duplicates" if unchanged else "revised"
    return row, outcome, prior_health != _health_identity(row, version)


def _compatible_group(left, right):
    return left != right and all(
        value is None or other is None or value == other
        for key, value in left.items() for other in (right[key],)
    )


def _isolate_ambiguous_groups(scope, scan, applied, now):
    # A prior null grouping may overlap a newly returned explicit dimension.
    # Keep both identities, but exclude their ambiguous amounts until a
    # subsequent snapshot explicitly enumerates both groups for their bucket.
    by_time = {}
    for row in applied:
        by_time.setdefault(row.event_at, {})[row.pk] = row
    changed = False
    for event, rows in by_time.items():
        prior_rows = ProviderUsageRecord.objects.select_for_update().filter(
            scope=scope, kind="OA_BUCKET", event_at=event, accepted_generation__lt=scan.generation,
        ).exclude(pk__in=rows)
        conflicts = {}
        for prior in prior_rows:
            for current in rows.values():
                if _compatible_group(prior.natural_identity["dimensions"], current.natural_identity["dimensions"]):
                    conflicts[prior.pk] = prior
                    conflicts[current.pk] = current
        for row in conflicts.values():
            changed |= row.attribution != Attribution.DISCREPANCY
            _mark_conflict(row, scope, scan, now)
    return changed


def _page_shape(page, scan, persisted):
    receipt = page.receipt
    if (
        receipt.scope != ProviderScope(scan.scope.provider, scan.scope.parent_scope_id)
        or receipt.interval != UTCInterval(scan.requested_start, scan.requested_end)
        or receipt.profile != scan.profile or receipt.requested_cursor != persisted.requested_cursor
        or type(receipt.terminal_page_seen) is not bool
        or receipt.terminal_page_seen != (page.next_cursor is None)
    ):
        raise UsageRejected(Code.CLAIM_STALE)
    from selahcue_api.apps.providers.adapters.usage_child import dg_page, valid_cursor

    observed_type = DeepgramRequestObservation if scan.scope.provider == "deepgram" else OpenAIUsageBucketObservation
    if any(type(item) is not observed_type for item in page.records):
        raise UsageRejected(Code.INVALID_RESPONSE)
    if page.next_cursor is not None:
        try:
            valid = (
                dg_page(page.next_cursor) == dg_page(persisted.requested_cursor) + 1
                if scan.scope.provider == "deepgram" else valid_cursor(page.next_cursor)
            )
        except (ValueError, TypeError):
            valid = False
        if not valid or (persisted.state != 'APPLIED' and UsagePageClaim.objects.filter(
            scan=scan, requested_cursor=page.next_cursor,
        ).exists()):
            raise UsageRejected(Code.INVALID_CURSOR)
    starts = receipt.oa_bucket_starts
    if observed_type is DeepgramRequestObservation:
        if starts or len(page.records) > 100 or any(
            not scan.requested_start <= item.created_at < scan.requested_end for item in page.records
        ):
            raise UsageRejected(Code.INVALID_RESPONSE)
        return []
    if len(starts) > 24 or len(page.records) > 1000 or len(set(starts)) != len(starts):
        raise UsageRejected(Code.INVALID_RESPONSE)
    if any(
        not isinstance(value, datetime) or value.utcoffset() != timedelta(0)
        or value.minute or value.second or value.microsecond
        or not scan.requested_start <= value < scan.requested_end for value in starts
    ) or any(
        item.start not in starts or item.end - item.start != timedelta(hours=1) for item in page.records
    ):
        raise UsageRejected(Code.INVALID_RESPONSE)
    epochs = sorted(int(value.timestamp()) for value in starts)
    for prior in UsagePageClaim.objects.filter(scan=scan, state="APPLIED").exclude(pk=persisted.pk).values_list(
        "oa_bucket_starts", flat=True,
    ):
        if set(epochs).intersection(prior):
            raise UsageRejected(Code.INVALID_RESPONSE)
    return epochs


def ingest_observations(page: UsagePage, scan_id, *, claim: UsageClaim, deadline_ns=None,
                        monotonic_ns=time.monotonic_ns) -> IngestResult:
    from .usage_tasks import bounded_transaction, require_usage_role

    require_usage_role()
    with bounded_transaction(deadline_ns=deadline_ns, monotonic_ns=monotonic_ns):
        scope_hint = UsageScan.objects.filter(pk=scan_id).values_list("scope_id", "scope__provider").first()
        if scope_hint is None or type(claim) is not UsageClaim:
            raise UsageRejected(Code.CLAIM_STALE)
        scope_id, provider_name = scope_hint
        now = timezone.now()
        provider = health.lock_provider(provider_name, now)
        prior_scopes = ProviderUsageRecord.objects.filter(
            provider=provider_name, request_id__in=[
                item.request_id for item in page.records if isinstance(item, DeepgramRequestObservation)
            ],
        ).values_list("scope_id", flat=True)
        affected_scope_ids = set(prior_scopes) | {scope_id}
        scopes = {
            scope.pk: scope for scope in UsageScope.objects.select_for_update().filter(
                pk__in=affected_scope_ids,
            ).order_by("provider", "parent_scope_id")
        }
        scope = scopes[scope_id]
        evaluations = {pk: health.scope_health(locked, now) for pk, locked in scopes.items()}
        scan = UsageScan.objects.select_for_update().get(pk=scan_id)
        persisted = UsagePageClaim.objects.select_for_update().filter(scan=scan, pk=claim.page_id).first()
        if persisted is None:
            raise UsageRejected(Code.CLAIM_STALE)
        now = timezone.now()
        starts = _page_shape(page, scan, persisted)
        digest = safe_digest("usage-page-v1", {
            "records": [_normalized(item) for item in page.records], "next": page.next_cursor,
            "terminal": page.receipt.terminal_page_seen, "oa_bucket_starts": starts,
        })
        if (
            persisted.state == "APPLIED" and scan.generation == claim.scan_generation
            and persisted.response_digest == digest
            and UsageWork.objects.filter(pk=claim.work_id, scan=scan, execution_generation=claim.work_generation).exists()
        ):
            return IngestResult(0, 0, len(page.records), 0)
        work_exists = UsageWork.objects.filter(
            pk=claim.work_id, scan=scan, scope=scope, kind="SCAN", state="RUNNING",
            execution_generation=claim.work_generation, lease_until__gt=now,
        ).exists()
        if (
            not work_exists or scan.state != ScanState.PARTIAL or scan.generation != claim.scan_generation
            or scan.page_ordinal != persisted.ordinal
            or scan.next_cursor != persisted.requested_cursor
            or persisted.state != "READING" or persisted.lease_id != claim.lease_id
            or persisted.lease_until is None or now >= persisted.lease_until
            or persisted.lane_fence != claim.lane_fence or scope.lane_fence != claim.lane_fence
            or scope.lane_scan_id != scan.pk or scope.lane_page_ordinal != persisted.ordinal
            or scope.lane_lease_id != claim.lease_id or scope.lane_lease_until != persisted.lease_until
        ):
            raise UsageRejected(Code.CLAIM_STALE)
        counts = {"inserted": 0, "revised": 0, "duplicates": 0, "unattributed": 0}
        changed_scopes = {scope_id}
        health_changes = set()
        dirty_ids = set()
        oa_applied = []
        for item in page.records:
            row, outcome, changed = _apply_fact(scope, scan, persisted, item, now)
            counts[outcome] += 1
            if provider_name == "openai" and row.accepted_generation == scan.generation:
                oa_applied.append(row)
            if row.attribution == Attribution.UNATTRIBUTED:
                counts["unattributed"] += 1
            if outcome != "duplicates":
                changed_scopes.add(row.scope_id)
                if row.mapping_id and provider_name == "deepgram":
                    dirty_ids.add(row.mapping.org_id)
            evaluation = evaluations[row.scope_id]
            window_start = evaluation.window_start or scan.requested_end - health.HEALTH_WINDOW
            if changed and row.event_at >= window_start:
                health_changes.add(row.scope_id)
        if oa_applied and _isolate_ambiguous_groups(scope, scan, oa_applied, now):
            if any(row.event_at >= (evaluations[scope_id].window_start or scan.requested_end - health.HEALTH_WINDOW)
                   for row in oa_applied):
                health_changes.add(scope_id)
        for pk in scopes:
            if pk in health_changes:
                generation = scan.generation if pk == scope_id else max(1, scopes[pk].next_scan_generation)
                health.invalidate(provider, evaluations[pk], generation, scan.requested_end, now)
            if pk in changed_scopes:
                bump_scope(scopes[pk], now)
        if provider_name == "deepgram":
            dirty_orgs(dirty_ids, now)

        persisted.state = "APPLIED"
        persisted.completed_at = persisted.first_receipt_at = persisted.updated_at = now
        persisted.response_digest, persisted.next_cursor = digest, page.next_cursor
        persisted.terminal, persisted.oa_bucket_starts = page.receipt.terminal_page_seen, starts
        persisted.lease_id = persisted.lease_until = persisted.lane_fence = persisted.retry_at = None
        persisted.save()
        scan.page_ordinal += 1
        if page.next_cursor is not None:
            UsagePageClaim.objects.create(
                scan=scan, ordinal=scan.page_ordinal, requested_cursor=page.next_cursor,
                created_at=now, updated_at=now,
            )
        scan.next_cursor = page.next_cursor
        scan.updated_at = now
        scan.save(update_fields=("page_ordinal", "next_cursor", "updated_at"))
        scope.lane_scan_id = scope.lane_page_ordinal = scope.lane_lease_id = scope.lane_lease_until = None
        scope.save(update_fields=("lane_scan", "lane_page_ordinal", "lane_lease_id", "lane_lease_until"))
        return IngestResult(**counts)


def attribute_scope_batch(scope_id: int, *, after: int | None, limit: int = 100, clock=timezone.now):
    from .usage_tasks import bounded_transaction, require_usage_role

    require_usage_role()
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Expected a bounded attribution batch")
    provider_name = UsageScope.objects.values_list("provider", flat=True).filter(pk=scope_id).first()
    if provider_name is None:
        return AttributionBatchResult(None, 0, 0, True)
    deadline = time.monotonic() + 10
    with bounded_transaction():
        now = clock()
        provider = health.lock_provider(provider_name, now)
        scope = health.lock_scope(provider_name, scope_id)
        evaluation = health.scope_health(scope, now)
        start = scope.attribution_after_record_id if after is None else after
        rows = list(ProviderUsageRecord.objects.select_for_update().filter(
            scope=scope, pk__gt=start or 0, mapping__isnull=True,
            attribution__in=(Attribution.UNATTRIBUTED, Attribution.DISCREPANCY),
        ).order_by("pk")[:limit])
        count, dirty, changes = 0, set(), 0
        for row in rows:
            if time.monotonic() >= deadline:
                break
            count += 1
            mapping, attribution = _attribute(scope, row.returned_project_id, row.returned_api_key_id)
            if mapping is None or row.issue == ObservationIssue.IDENTITY_CONFLICT:
                continue
            row.mapping, row.attribution, row.updated_at = mapping, attribution, now
            row.save(update_fields=("mapping", "attribution", "updated_at"))
            version = row.current_version
            if row.event_at >= (evaluation.window_start or version.source_interval_end - health.HEALTH_WINDOW):
                health.invalidate(provider, evaluation, row.accepted_generation, version.source_interval_end, now)
            if provider_name == "deepgram":
                if row.issue in (ObservationIssue.ANCIENT_FACT, ObservationIssue.PLACEMENT_GAP):
                    set_gap(scope, Code.PLACEMENT_GAP, now, record=row, org_id=mapping.org_id)
                dirty.add(mapping.org_id)
            changes += 1
        exhausted = count == len(rows) and len(rows) < limit
        next_after = None if exhausted else (rows[count - 1].pk if count else start)
        scope.attribution_after_record_id = next_after
        scope.save(update_fields=("attribution_after_record_id",))
        if changes:
            bump_scope(scope, now)
            dirty_orgs(dirty, now)
        return AttributionBatchResult(next_after, count, changes, exhausted)
