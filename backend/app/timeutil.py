"""Convert business-local calendar dates to UTC bounds, and UTC timestamps to local time."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import get_settings


def business_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().business_timezone)


def _local_midnight_utc(d: date) -> datetime:
    local = datetime.combine(d, time.min, tzinfo=business_tz())
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def local_date_range_to_utc(
    start: date | None, end: date | None
) -> tuple[datetime | None, datetime | None]:
    """[start 00:00 local, end+1 00:00 local) as naive-UTC bounds. `end` is inclusive."""
    lo = _local_midnight_utc(start) if start else None
    hi = _local_midnight_utc(end + timedelta(days=1)) if end else None
    return lo, hi


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(business_tz())


def today_local() -> date:
    return datetime.now(business_tz()).date()
