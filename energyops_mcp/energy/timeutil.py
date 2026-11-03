"""Timezone helpers: persist UTC, display America/Guatemala (UTC-6, no DST)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Guatemala")

INTERVAL_MINUTES = 15
INTERVALS_PER_DAY = 24 * 60 // INTERVAL_MINUTES  # 96


def local_datetime(d: date, minute_of_day: int) -> datetime:
    hour, minute = divmod(minute_of_day, 60)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=LOCAL_TZ)


def to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed; attach a timezone first")
    return dt.astimezone(UTC).isoformat()


def from_utc_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(LOCAL_TZ)


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=Saturday, 6=Sunday
