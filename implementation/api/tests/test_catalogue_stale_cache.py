"""QA PoC (Quinn, 86ak5t1h9): the two override guards that no shipped test can reach.

Both guards in `resolve_entitlement`'s override loop are unreachable in a FRESH resolution
because `CachedGrants` is built from the same read that would have excluded the row. The
only divergent path is a cache entry that outlives a SIGNAL-BYPASSING write (`QuerySet.
update()` fires no post_save, so `signals.bump_catalogue_revision` never runs) inside the
60s TTL. These two tests construct exactly that window and assert the guard still holds.
"""

from __future__ import annotations

import pytest

from selahcue_api.apps.catalogue.cache import GRANT_CACHE
from selahcue_api.apps.catalogue.models import GrantDimension, LicenseGrantOverride
from selahcue_api.apps.catalogue.services import current_revision, resolve_entitlement

from tests.test_entitlement_manifest_grants import _assign, _seed_license_key

pytestmark = pytest.mark.django_db

WATERMARK_KEY = "watermark"
SCREEN_KEY = "screen_outputs"


def _warm(key, dimension_key):
    """Resolve once so GRANT_CACHE holds this plan's map, and return (plan_pk, revision)."""
    first = resolve_entitlement(key)
    assert first.plan is not None, "the catalogue resolved no plan; the premise is gone"
    revision = current_revision()
    assert GRANT_CACHE.contains(first.plan.pk, revision), (
        "the plan map was not cached, so there is no stale window to test and the guard "
        "below cannot be exercised"
    )
    return first, first.plan.pk, revision


def test_a_STALE_cached_published_set_still_cannot_publish_an_unpublishable_dimension():
    key, _ = _seed_license_key(tag="qa-stale-pub")
    _assign(key, "PRO")
    dimension = GrantDimension.objects.get(key=WATERMARK_KEY)
    assert dimension.publish_in_manifest is True, "premise: this dimension starts publishable"

    first, plan_pk, revision = _warm(key, WATERMARK_KEY)
    assert WATERMARK_KEY in first.published_values, (
        "premise: the dimension must be PUBLISHED before the flip, or the cached `published` "
        "set never claims it and the discard arm is not reached"
    )

    # Signal-bypassing write: no post_save, so no revision bump and no cache invalidation.
    GrantDimension.objects.filter(pk=dimension.pk).update(publish_in_manifest=False)
    assert current_revision() == revision, (
        "the update bumped the catalogue revision, so the cache was invalidated and the "
        "STALE window this test depends on never opened"
    )
    assert GRANT_CACHE.contains(plan_pk, revision), (
        "the cache entry is gone, so resolution re-reads the dimension and the stale "
        "`published` set is never consulted — the discard arm went unexercised"
    )

    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=dimension,
        raw_value="true",
        granted_by_actor_id="staff_ops_1",
        reason="QA PoC: per-licence exception on a now-unpublishable dimension.",
    )

    second = resolve_entitlement(key)
    assert GRANT_CACHE.contains(plan_pk, revision), (
        "the entry expired mid-test; the resolution above was not served from the stale map"
    )
    assert second.values[WATERMARK_KEY] is True, (
        "positive control: the override must still APPLY to the resolved value — if it did "
        "not, the publish decision below is trivially safe and tests nothing"
    )
    assert WATERMARK_KEY not in second.published_values, (
        "a per-licence override PUBLISHED a dimension whose `publish_in_manifest` is False, "
        "by riding a cached `published` set built before the flip"
    )


def test_a_STALE_cached_known_set_still_cannot_apply_an_INACTIVE_dimensions_override():
    key, _ = _seed_license_key(tag="qa-stale-active")
    _assign(key, "PRO")
    dimension = GrantDimension.objects.get(key=SCREEN_KEY)
    assert dimension.is_active is True, "premise: this dimension starts active"

    first, plan_pk, revision = _warm(key, SCREEN_KEY)
    plan_value = first.values[SCREEN_KEY]
    assert plan_value == 5, f"premise: PRO grants 5 screen outputs, got {plan_value!r}"

    GrantDimension.objects.filter(pk=dimension.pk).update(is_active=False)
    assert current_revision() == revision, (
        "the update bumped the revision; the stale window never opened"
    )
    assert GRANT_CACHE.contains(plan_pk, revision), (
        "the cache entry is gone, so `known` is rebuilt without this key and the "
        "`dimension__is_active=True` filter went unexercised"
    )

    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=dimension,
        raw_value="9",
        granted_by_actor_id="staff_ops_1",
        reason="QA PoC: per-licence exception on a now-inactive dimension.",
    )

    second = resolve_entitlement(key)
    assert GRANT_CACHE.contains(plan_pk, revision), (
        "the entry expired mid-test; the resolution above was not served from the stale map"
    )
    assert second.values[SCREEN_KEY] == plan_value, (
        "an override on an INACTIVE dimension was applied, by riding a cached `known` set "
        f"built before the deactivation (expected the plan value {plan_value}, got "
        f"{second.values.get(SCREEN_KEY)!r})"
    )


def test_the_stale_window_is_real_positive_control():
    """Without this, both tests above could pass because the override never applies at all.

    Proves the cache genuinely serves a map built before a signal-bypassing edit: flip a
    dimension's PLAN value with `update()` and the resolution still reports the OLD value.
    """
    from selahcue_api.apps.catalogue.models import Plan, PlanGrant

    key, _ = _seed_license_key(tag="qa-stale-control")
    _assign(key, "PRO")
    first, plan_pk, revision = _warm(key, SCREEN_KEY)
    assert first.values[SCREEN_KEY] == 5

    PlanGrant.objects.filter(
        plan=Plan.objects.get(code="PRO"), dimension__key=SCREEN_KEY
    ).update(raw_value="99")
    assert current_revision() == revision, "the update bumped the revision"

    second = resolve_entitlement(key)
    assert second.values[SCREEN_KEY] == 5, (
        "the cache did NOT serve a stale map, so the two tests above are not exercising a "
        "stale `published`/`known` set either"
    )
