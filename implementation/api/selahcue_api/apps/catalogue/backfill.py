"""Bring pre-catalogue licences into the catalogue without changing what they grant.

Called by migration 0003, and callable directly against live models so the equivalence it
promises is testable without driving Django's migration executor
(`tests/test_catalogue_backfill_equivalence.py`).

**What "no change in what a current licence grants" means concretely.** Before this
catalogue existed, a licence carried exactly one enforced limit — `device_limit` — plus two
opaque labels (`feature_scope`, `territory`). Screens/outputs and NDI outputs were not
capped by anything, output carried no watermark, and hosted STT did not exist at all. So
freezing today's behaviour is:

    device instances   the licence's own `device_limit`, written as a per-licence override
    screen outputs     unlimited      (nothing capped them)
    NDI outputs        unlimited      (nothing capped them)
    watermark          off            (nothing drew one)
    STT minutes        0              (the hosted service does not exist yet)

Those five are the bridge plan's grants, seeded by migration 0002. STT at 0 rather than at
the free tier's 30 minutes is the deliberate reading of "no change": granting minutes
nobody has today would be a new cost, not a preserved entitlement. Moving an org onto a
real tier is a data action, and that is when its allowance starts.

Both steps are idempotent, so a re-run — or a partially applied migration — converges
rather than duplicating.
"""

from __future__ import annotations

from dataclasses import dataclass

# Rows are streamed and written in batches: a backfill must not load every licence key in
# the estate into memory at once (repo bounded-memory rule).
BATCH_SIZE = 500

# Stamped on every override this writes, and the only thing that distinguishes a row the
# backfill created from one an operator set by hand. Migration 0003's reverse scopes its
# delete by it, so reversing cannot silently discard an operator's deliberate override.
BACKFILL_REASON = "Pre-catalogue device_limit preserved verbatim (FR-544 migration)."


class BackfillPreconditionError(RuntimeError):
    """The catalogue reference data this backfill depends on is not present."""


@dataclass(frozen=True)
class BackfillResult:
    aliases_created: int
    overrides_created: int
    scopes_seen: int
    licenses_seen: int


def backfill_licenses_into_catalogue(
    *,
    license_key_model,
    plan_model,
    alias_model,
    dimension_model,
    override_model,
) -> BackfillResult:
    """Map every existing `feature_scope` to the bridge plan and pin every seat cap.

    The bridge plan and the seat dimension are found by their DATA flags — `is_fallback`
    and `governs_instance_limit` — never by a code literal, so this function contains no
    tier name at all.
    """
    bridge_plan = plan_model.objects.filter(is_fallback=True).first()
    if bridge_plan is None:
        raise BackfillPreconditionError(
            "no fallback plan exists; catalogue reference data must be seeded first"
        )
    seat_dimension = dimension_model.objects.filter(governs_instance_limit=True).first()
    if seat_dimension is None:
        raise BackfillPreconditionError(
            "no dimension governs the instance limit; catalogue reference data must be seeded first"
        )

    scopes = {
        (scope or "").strip().upper()
        for scope in license_key_model.objects.values_list("feature_scope", flat=True).distinct()
    }
    scopes.discard("")

    aliases_created = 0
    for scope in sorted(scopes):
        _alias, created = alias_model.objects.get_or_create(
            feature_scope=scope, defaults={"plan": bridge_plan}
        )
        aliases_created += int(created)

    # Counted as a row delta rather than from what `bulk_create` hands back: with
    # `ignore_conflicts=True` several backends (SQLite among them) return the objects with
    # their primary keys unset, so inspecting the returned list reports zero creations even
    # when every row landed.
    overrides_before = override_model.objects.count()

    licenses_seen = 0
    pending: list = []
    queryset = license_key_model.objects.only("id", "device_limit").order_by("id")
    for license_key in queryset.iterator(chunk_size=BATCH_SIZE):
        licenses_seen += 1
        pending.append(
            override_model(
                license_key_id=license_key.id,
                dimension_id=seat_dimension.id,
                raw_value=str(license_key.device_limit),
                reason=BACKFILL_REASON,
            )
        )
        if len(pending) >= BATCH_SIZE:
            _flush(override_model, pending)
            pending = []
    _flush(override_model, pending)

    return BackfillResult(
        aliases_created=aliases_created,
        overrides_created=override_model.objects.count() - overrides_before,
        scopes_seen=len(scopes),
        licenses_seen=licenses_seen,
    )


def _flush(override_model, pending: list) -> None:
    """Insert a batch, skipping licences that already carry an override for the dimension.

    `ignore_conflicts` is what makes a re-run converge: the unique (licence, dimension)
    constraint absorbs rows written by an earlier pass, and an operator's hand-set override
    is never overwritten by the backfill.
    """
    if not pending:
        return
    override_model.objects.bulk_create(pending, batch_size=BATCH_SIZE, ignore_conflicts=True)
