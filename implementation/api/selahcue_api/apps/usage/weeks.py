"""Calendar-local Monday boundaries represented by immutable UTC instants."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from selahcue_api.apps.usage.contracts import UTCInterval

logger = logging.getLogger(__name__)
WEEK = timedelta(days=7)


@dataclass(frozen=True)
class LocalWeek(UTCInterval):
    monday: date
    tz_name: str
    admissions_start_at: datetime

    def __post_init__(self):
        super().__post_init__()
        if (
            self.admissions_start_at.utcoffset() != timedelta(0)
            or not self.start <= self.admissions_start_at < self.end
        ):
            raise ValueError("Expected an admission start within UTC accounting bounds")


def utc_instant(at: datetime) -> datetime:
    if at.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    return at.astimezone(UTC)


def _midnight(day: date, zone: tzinfo) -> datetime:
    local = datetime.combine(day, time.min)
    lower, upper = sorted(local.replace(tzinfo=zone, fold=fold).astimezone(UTC) for fold in (0, 1))

    def local_time(instant: datetime) -> datetime:
        return instant.astimezone(zone).replace(tzinfo=None)

    # An ambiguous midnight takes the first occurrence. A nonexistent midnight has one
    # candidate on each side of the jump: find the first valid instant, even if the
    # offset change started before midnight and ends after it.
    if local_time(lower) == local:
        return lower
    while upper - lower > timedelta(microseconds=1):
        middle = lower + (upper - lower) // 2
        if local_time(middle) < local:
            lower = middle
        else:
            upper = middle
    return upper


def local_week(
    tz_name: str, at: datetime, *, previous: tuple[date, datetime] | None = None,
) -> LocalWeek:
    """Project frozen accounting and admission bounds after a previous local label.

    Reconciliation can use this geometry for its actual provider timestamp. If
    the adjacent label's local midnight follows the previous frozen boundary,
    start accounting at that boundary and open new admissions at local midnight.
    """
    try:
        zone = UTC if tz_name == "UTC" else ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        logger.warning("Org weekly usage has an invalid time zone, falling back to UTC")
        zone, tz_name = UTC, "UTC"
    local_date = utc_instant(at).astimezone(zone).date()
    monday = local_date - timedelta(days=local_date.weekday())
    if previous is not None:
        previous_monday, previous_end = previous
        monday = max(monday, previous_monday + WEEK)

    midnight = _midnight(monday, zone)
    end = _midnight(monday + WEEK, zone)
    start = midnight
    if previous is not None:
        start = previous_end if monday == previous_monday + WEEK else max(midnight, previous_end)
    return LocalWeek(start, end, monday, tz_name, max(start, midnight))
