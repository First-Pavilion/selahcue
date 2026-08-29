"""Bounded, revision-stamped cache for resolved plan grant maps.

Two properties matter and they pull against each other:

*   **Bounded** (repo rule: no unbounded caches). The entry COUNT is capped, not a byte
    budget — a byte budget alone admits unboundedly many tiny entries, which unbounds
    lookup cost. Per-key hit counters live INSIDE the entry, so eviction reclaims them too;
    a side table of counters would itself be the unbounded thing.
*   **Never stale.** FR-544 says changing a grant value takes effect with no release. A
    cache that outlives the edit defeats exactly that. Two independent mechanisms, because
    neither covers the other's blind spot:

    - Every entry is stamped with the catalogue revision it was built from, and any ORM
      write bumps that counter (signals.py). This is immediate and covers the admin, the
      services and every `.save()`.
    - A short TTL backstops it. `QuerySet.update()` and raw SQL fire no signals, so an
      operator editing rows that way would otherwise be served the old grants until the
      process restarted. The TTL bounds that window to seconds instead of forever.

Deliberately per-process and in-memory: it holds resolved values only, is rebuilt from one
query, and needs no cache backend to be correct.

**Entries are shared across every tenant on a plan, so what goes in must be immutable.**
Callers store a read-only mapping (`types.MappingProxyType`); a caller that then forgets to
copy before applying one licence's overrides gets a `TypeError` instead of quietly writing
that licence's entitlement into the entry every other org on the plan reads next.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Mapping

# Cap on distinct plans held at once. Least-recently-used is evicted beyond it; an evicted
# plan still resolves, it just pays the query again.
MAX_CACHE_ENTRIES = 64

# Backstop for signal-bypassing writes (see the module docstring). Short enough that an
# operator does not conclude the edit "did not work", long enough to still be a cache.
CACHE_TTL_SECONDS = 60.0

# Pinned beside the constants so changing one cannot silently turn its test vacuous. Below
# 2 entries there is nothing to evict *from*; a non-positive TTL would expire every entry
# instantly, making the hit assertions unreachable and the cache a no-op.
assert MAX_CACHE_ENTRIES >= 2, "MAX_CACHE_ENTRIES must be large enough for eviction to be observable"
assert MAX_CACHE_ENTRIES <= 4096, "MAX_CACHE_ENTRIES must stay a bound, not a formality"
assert CACHE_TTL_SECONDS > 0, "a non-positive TTL would disable the cache entirely"


@dataclass
class _Entry:
    revision: int
    values: Mapping[str, Any]
    stored_at: float
    hits: int = 0


class BoundedGrantCache:
    """LRU over plan id → resolved grant map, valid for one catalogue revision."""

    def __init__(
        self,
        *,
        max_entries: int = MAX_CACHE_ENTRIES,
        ttl_seconds: float = CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        # Injected, like every other time-dependent thing in this repo, so expiry is
        # asserted deterministically rather than by sleeping.
        self._clock = clock
        self._entries: OrderedDict[int, _Entry] = OrderedDict()
        self._revision: int | None = None
        self._lock = threading.Lock()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    def _live_entry(self, plan_id: int, revision: int) -> _Entry | None:
        """The entry for this key IF it would actually be served, else None.

        One predicate shared by `get`, `contains` and `hits_for`, so an inspector can never
        report an entry as resident that `get` would refuse. Reporting residency on a
        superseded or expired entry would let a residency assertion pass on a dead one —
        which is exactly the sort of test that guards nothing.
        """
        if self._revision != revision:
            return None
        entry = self._entries.get(plan_id)
        if entry is None:
            return None
        if self._clock() - entry.stored_at >= self._ttl_seconds:
            return None
        return entry

    def contains(self, plan_id: int, revision: int) -> bool:
        """Whether this exact key would be served. The entity assertion, not a byte proxy."""
        with self._lock:
            return self._live_entry(plan_id, revision) is not None

    def hits_for(self, plan_id: int, revision: int) -> int | None:
        """Hits recorded for ONE key, or None when the key would not be served.

        Per-key on purpose: a global counter lets a sibling test's hits mask a miss on the
        key under test, which is precisely how a cache test stops testing anything.
        """
        with self._lock:
            entry = self._live_entry(plan_id, revision)
            return None if entry is None else entry.hits

    def get(self, plan_id: int, revision: int) -> Mapping[str, Any] | None:
        with self._lock:
            if self._revision != revision:
                # A catalogue edit landed: everything held is from a superseded revision.
                self._entries.clear()
                self._revision = revision
                return None
            entry = self._live_entry(plan_id, revision)
            if entry is None:
                # Expired entries are dropped rather than refreshed, so a signal-bypassing
                # edit can never be served indefinitely.
                self._entries.pop(plan_id, None)
                return None
            entry.hits += 1
            self._entries.move_to_end(plan_id)
            return entry.values

    def put(self, plan_id: int, revision: int, values: Mapping[str, Any]) -> None:
        with self._lock:
            if self._revision != revision:
                self._entries.clear()
                self._revision = revision
            self._entries[plan_id] = _Entry(
                revision=revision, values=values, stored_at=self._clock()
            )
            self._entries.move_to_end(plan_id)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._revision = None


# Module-level instance used by services.resolve_entitlement.
GRANT_CACHE = BoundedGrantCache()


def grant_cache_hits_for(plan_id: int, revision: int) -> int | None:
    """Per-key hit accessor for tests. None means "this key would not be served"."""
    return GRANT_CACHE.hits_for(plan_id, revision)
