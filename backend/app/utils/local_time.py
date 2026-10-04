"""A society's own clock.

Timestamps are stored as naive UTC (`datetime.utcnow()`), but the date a staff
member punches in on, a shift's start and the times written on a printed sheet
are all the society's local time. These helpers convert between the two.
"""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Asia/Kolkata"


def zone(name) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def local_now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def local_today(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


def utc_naive(dt: datetime) -> datetime:
    """Any datetime as the naive UTC the database holds (naive input is already UTC)."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    """A stored (naive UTC) datetime on the society's clock."""
    return dt.replace(tzinfo=timezone.utc).astimezone(tz) if dt.tzinfo is None else dt.astimezone(tz)


def local_to_utc_naive(day: date, clock: time, tz: ZoneInfo) -> datetime:
    """`clock` on `day` as written on a sheet in the society's time, as naive UTC."""
    return utc_naive(datetime.combine(day, clock.replace(tzinfo=None), tzinfo=tz))


def iso_utc(dt):
    """A stored datetime as ISO text with an explicit UTC `Z`, so a client shows it
    in its own zone. Naive values are UTC."""
    if dt is None:
        return None
    return utc_naive(dt).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
