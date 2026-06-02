import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_DAYS_RE = re.compile(r"(?:last|past)\s+(\d+)\s+days?", re.IGNORECASE)
_WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri", "sat", "sun",
}
_WEEKDAY_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}
_UTC = ZoneInfo("UTC")


def _resolve_tz(tz: str | None) -> ZoneInfo:
    if tz is not None:
        try:
            return ZoneInfo(tz)
        except (ZoneInfoNotFoundError, KeyError):
            pass
    return _UTC


def extract_range(text: str, tz: str | None = None, now: datetime | None = None) -> tuple[datetime, datetime, str] | None:
    if now is None:
        tz_obj = _resolve_tz(tz)
        now = datetime.now(tz_obj)
    elif now.tzinfo is not None:
        tz_obj = now.tzinfo
    else:
        tz_obj = _resolve_tz(tz)
        now = now.replace(tzinfo=tz_obj)

    local_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    lower = text.strip().lower()

    if lower == "today":
        start = local_midnight
        end = now
        start_utc = start.astimezone(_UTC).replace(tzinfo=None)
        end_utc = end.astimezone(_UTC).replace(tzinfo=None)
        return (start_utc, end_utc, "today")

    if lower == "yesterday":
        yesterday = local_midnight - timedelta(days=1)
        start = yesterday
        end = local_midnight
        start_utc = start.astimezone(_UTC).replace(tzinfo=None)
        end_utc = end.astimezone(_UTC).replace(tzinfo=None)
        return (start_utc, end_utc, "yesterday")

    if lower == "this week":
        weekday = local_midnight.weekday()
        start = local_midnight - timedelta(days=weekday)
        end = now
        start_utc = start.astimezone(_UTC).replace(tzinfo=None)
        end_utc = end.astimezone(_UTC).replace(tzinfo=None)
        return (start_utc, end_utc, "this week")

    m = _DAYS_RE.search(lower)
    if m:
        n = int(m.group(1))
        start = now - timedelta(days=n)
        start_utc = start.astimezone(_UTC).replace(tzinfo=None)
        end_utc = now.astimezone(_UTC).replace(tzinfo=None)
        return (start_utc, end_utc, f"the last {n} day{'s' if n != 1 else ''}")

    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text.strip())
    if iso_match:
        y, mth, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        start = datetime(y, mth, d, tzinfo=tz_obj)
        end = start + timedelta(days=1)
        start_utc = start.astimezone(_UTC).replace(tzinfo=None)
        end_utc = end.astimezone(_UTC).replace(tzinfo=None)
        return (start_utc, end_utc, f"on {text.strip()}")

    words = lower.split()
    for w in words:
        if w in _WEEKDAYS:
            target_weekday = _WEEKDAY_MAP[w]
            current_weekday = local_midnight.weekday()
            delta = (target_weekday - current_weekday) % 7
            if delta == 0:
                delta = 7
            start = local_midnight - timedelta(days=7 - delta)
            end = start + timedelta(days=1)
            start_utc = start.astimezone(_UTC).replace(tzinfo=None)
            end_utc = end.astimezone(_UTC).replace(tzinfo=None)
            return (start_utc, end_utc, f"on {w}")

    return None
