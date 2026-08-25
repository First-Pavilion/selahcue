"""Bump the catalogue revision whenever catalogue data changes.

FR-544 promises that changing a grant value takes effect with no release. The in-process
grant cache is stamped with this counter, so an operator's UPDATE is picked up by every
worker on its next resolution — not on its next restart.

**The bump happens inside the writer's transaction, not on commit.** Two reasons. Other
connections do not see the new counter until the write commits, so they keep serving the
old grants from cache for exactly as long as the old grants are still the truth; and a
rollback reverts the counter along with the change, which is right. Deferring to
`on_commit` would instead mean the bump never runs at all inside a transaction that is
rolled back — including every test wrapped in `django_db` — turning a stale cache into a
bug that only shows up under test.

`F("revision") + 1` rather than read-modify-write, so concurrent writers cannot lose an
increment. The number itself never matters, only that it changed.
"""

from __future__ import annotations

import logging

from django.db.models import F
from django.db.models.signals import post_delete, post_save

from selahcue_api.apps.catalogue.models import (
    CatalogueRevision,
    GrantDimension,
    LicenseGrantOverride,
    LicensePlanAssignment,
    Plan,
    PlanGrant,
    PlanScopeAlias,
)

logger = logging.getLogger(__name__)

# Every model whose contents can change a resolved entitlement. `CatalogueRevision` is
# deliberately absent — it is the counter, not catalogue data, and watching it would
# recurse.
WATCHED_MODELS = (
    Plan,
    GrantDimension,
    PlanGrant,
    PlanScopeAlias,
    LicensePlanAssignment,
    LicenseGrantOverride,
)

_DISPATCH_UID = "selahcue_catalogue.bump_revision"


def bump_catalogue_revision() -> None:
    """Increment the singleton counter, creating it if this is the first write."""
    try:
        updated = CatalogueRevision.objects.filter(pk=CatalogueRevision.SINGLETON_PK).update(
            revision=F("revision") + 1
        )
        if not updated:
            CatalogueRevision.objects.get_or_create(
                pk=CatalogueRevision.SINGLETON_PK, defaults={"revision": 1}
            )
    except Exception:  # pragma: no cover - a cache-invalidation failure must not fail the write
        logger.exception("could not bump the catalogue revision; caches may serve one stale read")


def _bump_on_catalogue_change(sender, **kwargs) -> None:
    bump_catalogue_revision()


def connect_catalogue_signals() -> None:
    """Wire the receivers, once per model. Called from the app's `ready()`."""
    for model in WATCHED_MODELS:
        # dispatch_uid makes this idempotent: `ready()` can run more than once (management
        # commands, autoreload) and double-connected receivers would double-bump.
        post_save.connect(_bump_on_catalogue_change, sender=model, dispatch_uid=_DISPATCH_UID)
        post_delete.connect(_bump_on_catalogue_change, sender=model, dispatch_uid=_DISPATCH_UID)
