"""Bounded cumulative diagnostics for the API licence lifecycle tests."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import isfinite


_LABELS = {
    "tests/test_license_revoke_extend.py": "test_license_revoke_extend.py",
    "tests/test_license_suspend_reinstate.py": "test_license_suspend_reinstate.py",
}
_PHASES = ("setup", "call", "teardown")
_BUCKET_SIZE = 50


class ApiPhaseTimingBudget:
    """Allow at most twelve diagnostic records across pytest sessions."""

    __slots__ = ("_remaining",)

    def __init__(self) -> None:
        self._remaining = 12

    def claim(self, *, reserved: int = 0) -> bool:
        if self._remaining <= reserved:
            return False
        self._remaining -= 1
        return True


# Pytest can reload conftest for a new session. This imported helper stays cached.
_PROCESS_BUDGET = ApiPhaseTimingBudget()


@dataclass(slots=True)
class _FileTimings:
    selected: int = 0
    reported_at: int = 0
    finalized: bool = False
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(_PHASES, 0))
    seconds: dict[str, float] = field(default_factory=lambda: dict.fromkeys(_PHASES, 0.0))

    def line(self, label: str) -> str:
        self.reported_at = self.counts["teardown"]
        phases = " ".join(
            f"{phase}_reports={self.counts[phase]} {phase}_seconds={self.seconds[phase]:.9g}"
            for phase in _PHASES
        )
        return (
            f"SELAHCUE_API_PHASE_TIMING_V1 file={label} selected={self.selected} "
            f"completed_teardowns={self.reported_at} {phases}"
        )

    def finish(self, label: str, budget: ApiPhaseTimingBudget) -> str | None:
        if self.finalized:
            return None
        self.finalized = True
        if self.counts["teardown"] != self.reported_at and budget.claim():
            return self.line(label)
        return None


class ApiPhaseTimings:
    """Track report counts and finite duration sums for one pytest session."""

    __slots__ = ("_files", "_budget")

    def __init__(
        self, selected_nodeids: Iterable[str], *, budget: ApiPhaseTimingBudget | None = None
    ) -> None:
        self._files = {path: _FileTimings() for path in _LABELS}
        self._budget = _PROCESS_BUDGET if budget is None else budget
        for nodeid in selected_nodeids:
            if totals := self._files.get(nodeid.split("::", 1)[0]):
                totals.selected += 1

    def observe(self, nodeid: str, phase: str, duration: float) -> None:
        totals = self._files.get(nodeid.split("::", 1)[0])
        if totals is None or not totals.selected or totals.finalized:
            return
        totals.counts[phase] += 1
        summed = totals.seconds[phase] + duration
        if isfinite(summed):
            totals.seconds[phase] = summed

    def progress(self, nodeid: str) -> str | None:
        """Return a due record once pytest has logged the complete item."""
        path = nodeid.split("::", 1)[0]
        totals = self._files.get(path)
        if totals is None or totals.finalized:
            return None
        completed = totals.counts["teardown"]
        if completed == totals.reported_at:
            return None
        if completed == totals.selected:
            return totals.finish(_LABELS[path], self._budget)
        if completed % _BUCKET_SIZE == 0:
            reserved = sum(
                file.selected > 0 and not file.finalized for file in self._files.values()
            )
            if self._budget.claim(reserved=reserved):
                return totals.line(_LABELS[path])
        return None

    def finish(self) -> list[str]:
        """Flush tails when pytest stops before completing its selection."""
        records = []
        for path, totals in self._files.items():
            if record := totals.finish(_LABELS[path], self._budget):
                records.append(record)
        return records
