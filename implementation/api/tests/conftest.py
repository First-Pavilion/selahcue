"""Process-wide test fixtures.

**Deliberately narrow.** The shipped slices each build their own module-local seeding
helpers rather than sharing them, and that convention stands — nothing here seeds anything.
This file exists for one thing that module-local fixtures structurally cannot do.

`selahcue_api.apps.catalogue.cache.GRANT_CACHE` is a PROCESS global. It is not part of the
database, so `django_db`'s per-test rollback does not touch it, and its key (a plan primary
key) is stable across rollbacks — so an entry written by one test can be served to the next
one under a recycled id. Only the suites that happen to remember an autouse fixture were
protected; every other suite that calls `resolve_entitlement`, directly or through the
entitlement manifest, was not. None of them assert on grants today, which is exactly why a
stale map would have gone unnoticed rather than failed loudly.

A per-module fixture cannot fix that, because the suite that needs protecting is the one
whose author never thought about this cache.
"""

import pytest


@pytest.fixture(autouse=True)
def _cold_catalogue_grant_cache():
    from selahcue_api.apps.catalogue.cache import GRANT_CACHE

    GRANT_CACHE.clear()
    yield
    GRANT_CACHE.clear()
