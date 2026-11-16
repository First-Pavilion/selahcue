"""One no-lock read of STT publication dependencies and provider health."""
from datetime import datetime
from uuid import UUID

from django.db import connection

from .contracts import SttReadiness
from .health import HEALTH_SQL, result_time, utc_parameter


_STT_SQL = HEALTH_SQL + """
, org_input(org_id, mapping_id) AS (VALUES (%s, %s)),
publication AS (
    SELECT p.*, org_state.dirty_revision, org_state.applied_revision,
           mapping.activated_at, mapping.parent_scope_id
      FROM org_input req
      JOIN selahcue_usage_sttorgreadiness p ON p.org_id = req.org_id AND p.mapping = req.mapping_id
      LEFT JOIN selahcue_usage_usageorgstate org_state ON org_state.org_id = p.org_id
      LEFT JOIN selahcue_providers_providercredential mapping
        ON mapping.id = p.mapping AND mapping.org_id = p.org_id
       AND mapping.provider = 'deepgram' AND mapping.state = 'ACTIVE'
),
vector AS (
    SELECT v.scope_revision, v.coverage_valid_until, v.observed_through, s.scope_id,
           s.revision AS live_revision, enrolled.parent_scope_id
      FROM publication p JOIN selahcue_usage_sttorgreadinessscope v ON v.publication_id = p.org_id
      JOIN selahcue_usage_sttscopereadiness s ON s.id = v.scope_id
      JOIN selahcue_usage_usagescope enrolled ON enrolled.id = s.scope_id AND enrolled.provider = 'deepgram'
),
fragments AS (
    SELECT observed.scope_id, MAX(c.required_end) AS through,
        MIN(observed.scan_started_at) AS original_start,
        MIN(/* fragment_expiry */) AS original_expiry,
        SUM(CASE WHEN observed.start > c.required_start OR observed.end < c.required_end
                      OR observed.profile <> 'DG_LISTEN_V1' THEN 1 ELSE 0 END) AS invalid
      FROM publication p
      JOIN selahcue_usage_sttorgcoverage c ON c.publication_id = p.org_id
      JOIN selahcue_usage_usageobservedinterval observed ON observed.id = c.observed_interval_id
     GROUP BY observed.scope_id
),
vector_check AS (
    SELECT COUNT(*) AS entries,
        MIN(vector.coverage_valid_until) AS valid_until,
        MIN(vector.observed_through) AS observed_through,
        COALESCE(SUM(CASE WHEN vector.parent_scope_id = p.parent_scope_id THEN 1 ELSE 0 END), 0) AS active_scope,
        COALESCE(SUM(CASE WHEN vector.scope_revision <> vector.live_revision
                             OR fragments.scope_id IS NULL OR fragments.invalid > 0
                             OR fragments.through <> vector.observed_through
                             OR fragments.original_expiry <> vector.coverage_valid_until
                             OR fragments.original_start < p.activated_at THEN 1 ELSE 0 END), 0) AS changed
      FROM vector CROSS JOIN publication p LEFT JOIN fragments ON fragments.scope_id = vector.scope_id
),
required_pending AS (
    SELECT 1
      FROM publication p
      JOIN selahcue_usage_usagescanrequirement req ON req.org_id = p.org_id
      JOIN selahcue_usage_usagescan scan ON scan.id = req.scan_id
      JOIN vector ON vector.scope_id = scan.scope_id
     WHERE req.kind IN ('INITIAL', 'CURRENT', 'OPEN') AND scan.state IN ('PARTIAL', 'FAILED')
       AND scan.page_ordinal > 0 AND (req.mapping IS NULL OR req.mapping = p.mapping)
       AND EXISTS (
           SELECT 1 FROM selahcue_usage_sttorgcoverage c
           JOIN selahcue_usage_usageobservedinterval oi ON oi.id = c.observed_interval_id
           WHERE c.publication_id = p.org_id AND oi.scope_id = scan.scope_id
             AND c.required_start < req.required_end AND req.required_start < c.required_end
       )
       AND NOT EXISTS (
           SELECT 1 FROM selahcue_usage_usageobservedinterval replacement
           JOIN selahcue_usage_usagescan completed ON completed.id = replacement.scan_id
            WHERE replacement.scope_id = scan.scope_id AND completed.generation > scan.generation
              AND replacement.start <= req.required_start AND replacement.end >= req.required_end
       )
)
SELECT publication.publication_revision, publication.observed_through, publication.valid_until,
  CASE
    WHEN hp.reason = 'THRESHOLD' THEN 'unattributed_limit'
    WHEN publication.placement_gap OR EXISTS (
          SELECT 1 FROM selahcue_usage_usagecoveragegap gap WHERE gap.org_id = org_input.org_id
            AND gap.state = 'OPEN' AND gap.reason = 'PLACEMENT_GAP'
        ) THEN 'placement_gap'
    WHEN publication.org_id IS NOT NULL AND (
         (hp.reason IS NOT NULL AND hp.reason <> 'COVERAGE_STALE')
         OR hp.revision IS NULL OR publication.health_revision <> hp.revision
         OR publication.activated_at IS NULL OR publication.dirty_revision IS NULL
         OR publication.applied_revision <> publication.dirty_revision
         OR publication.org_dirty_revision <> publication.dirty_revision
         OR v.changed > 0 OR EXISTS (SELECT 1 FROM required_pending)
        ) THEN 'reconciliation_pending'
    WHEN publication.valid_until <= input.checked_at OR v.valid_until <= input.checked_at
         OR (publication.org_id IS NOT NULL AND hp.reason = 'COVERAGE_STALE')
        THEN 'coverage_stale'
    WHEN publication.org_id IS NULL OR v.entries = 0 OR v.active_scope <> 1
         OR v.observed_through <> publication.observed_through
         OR publication.valid_until > v.valid_until OR publication.valid_until > hp.valid_until
        THEN 'coverage_missing'
  END
FROM health_projection hp CROSS JOIN input CROSS JOIN org_input CROSS JOIN vector_check v
LEFT JOIN publication ON 1=1
"""


def read_stt_readiness(*, org_id: int, mapping_id: UUID, at: datetime) -> SttReadiness:
    if type(org_id) is not int or org_id <= 0 or type(mapping_id) is not UUID:
        raise ValueError("Invalid STT readiness identity")
    expiry = (
        "django_format_dtdelta('+', observed.scan_started_at, 300000000)"
        if connection.vendor == "sqlite"
        else "(observed.scan_started_at + INTERVAL '300 seconds')"
    )
    sql = _STT_SQL.replace("/* fragment_expiry */", expiry)
    with connection.cursor() as cursor:
        cursor.execute(sql, [
            "deepgram", utc_parameter(at), org_id, connection.ops.adapt_unknown_value(mapping_id)
            if connection.vendor != "sqlite" else mapping_id.hex,
        ])
        revision, through, expiry, reason = cursor.fetchone()
    status = "current_observed" if reason is None else "not_initialized" if revision is None and reason == "coverage_missing" else "stale"
    return SttReadiness(org_id, mapping_id, status, at, result_time(through), result_time(expiry), revision, reason)
