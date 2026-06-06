import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_DAYS_RE = re.compile(r"(?:last|past)\s+(\d+)\s+days?", re.IGNORECASE)
_FUTURE_DAYS_RE = re.compile(r"\bin\s+(\d+)\s+(days?|weeks?|months?)\b", re.IGNORECASE)
_TIME_RE = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
_MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH_NAMES_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTH_MAP.keys(), key=len, reverse=True)) + r")\s+(\d{1,2})\b",
    re.IGNORECASE,
)
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

# Phase 24: a query is about *due dates* (not when something was saved) when it
# mentions any of these. This is what separates "what's due today" (filter on
# due_at) from "what did I save today" (filter on created_at).
_DUE_INTENT_RE = re.compile(
    r"\b(due|deadlines?|overdue|to-?do|to do|tasks?|reminders?|upcoming|"
    r"owe|need(?:s)?\s+to\s+do|have\s+to\s+do|supposed\s+to|schedule[ds]?|"
    r"plan(?:ned)?|calendar|events?|appointments?|meetings?)\b",
    re.IGNORECASE,
)

# When a query contains strong creation-time words it is asking about memories
# that were *saved*, not about what is *due* — even if planning vocab is present.
# e.g. "what tasks did I save this week?" → saved, not due.
_CREATION_INTENT_RE = re.compile(
    r"\b(saved?|stored?|told|tell(?:s|ing)?|noted?|recorded?|added|"
    r"wr(?:ote|ite|itten|iting)|mentioned)\b",
    re.IGNORECASE,
)


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

    # Match these as words anywhere in the question ("what did I tell you today?"),
    # not just as the whole message.
    if re.search(r"\btoday\b", lower):
        start = local_midnight
        end = now
        start_utc = start.astimezone(_UTC).replace(tzinfo=None)
        end_utc = end.astimezone(_UTC).replace(tzinfo=None)
        return (start_utc, end_utc, "today")

    if re.search(r"\byesterday\b", lower):
        yesterday = local_midnight - timedelta(days=1)
        start = yesterday
        end = local_midnight
        start_utc = start.astimezone(_UTC).replace(tzinfo=None)
        end_utc = end.astimezone(_UTC).replace(tzinfo=None)
        return (start_utc, end_utc, "yesterday")

    if re.search(r"\bthis\s+week\b", lower):
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


def extract_due_range(
    text: str, tz: str | None = None, now: datetime | None = None
) -> tuple[datetime, datetime, str] | None:
    """For due-date questions, return the [start, end) window (naive UTC) to filter
    `due_at` on, plus a human label. Returns None if the text isn't about due dates.

    Unlike `extract_range` (which is about when memories were *created*), this is
    about when things are *due* and is the path for "what's due today / this week".
    """
    if not _DUE_INTENT_RE.search(text):
        return None
    # "what tasks did I save this week?" has planning vocab but is asking about
    # creation time, not due time.  Creation-time words override the due intent.
    if _CREATION_INTENT_RE.search(text):
        return None

    if now is None:
        tz_obj = _resolve_tz(tz)
        now = datetime.now(tz_obj)
    elif now.tzinfo is not None:
        tz_obj = now.tzinfo
    else:
        tz_obj = _resolve_tz(tz)
        now = now.replace(tzinfo=tz_obj)

    local_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    far_past = local_midnight - timedelta(days=3650)
    lower = text.lower()

    if re.search(r"\boverdue\b", lower):
        start, end, label = far_past, now, "overdue"
    elif re.search(r"\btomorrow\b", lower):
        day = local_midnight + timedelta(days=1)
        start, end, label = day, day + timedelta(days=1), "tomorrow"
    elif re.search(r"\btoday\b", lower):
        # The whole of today, including items due earlier in the day.
        start, end, label = local_midnight, local_midnight + timedelta(days=1), "today"
    elif re.search(r"\bnext\s+week\b", lower):
        week_start = local_midnight - timedelta(days=local_midnight.weekday()) + timedelta(days=7)
        start, end, label = week_start, week_start + timedelta(days=7), "next week"
    elif re.search(r"\bthis\s+week\b", lower):
        week_start = local_midnight - timedelta(days=local_midnight.weekday())
        start, end, label = week_start, week_start + timedelta(days=7), "this week"
    else:
        # Generic "what's due / what do I have to do" → overdue + the next 7 days.
        start, end, label = far_past, local_midnight + timedelta(days=8), "soon"

    start_utc = start.astimezone(_UTC).replace(tzinfo=None)
    end_utc = end.astimezone(_UTC).replace(tzinfo=None)
    return (start_utc, end_utc, label)


def _apply_time(dt: datetime, lower: str) -> datetime:
    """If `lower` contains 'at X am/pm', return dt with that time applied."""
    m = _TIME_RE.search(lower)
    if not m:
        return dt
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    meridiem = m.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)


def extract_due(text: str, tz: str | None = None, now: datetime | None = None) -> datetime | None:
    """Return the first future due-date found in `text`, as a naive UTC datetime, or None."""
    if now is None:
        tz_obj = _resolve_tz(tz)
        now = datetime.now(tz_obj)
    elif now.tzinfo is None:
        tz_obj = _resolve_tz(tz)
        now = now.replace(tzinfo=tz_obj)
    else:
        tz_obj = now.tzinfo

    local_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    lower = text.lower()

    def _future_utc(dt: datetime) -> datetime | None:
        if dt > now:
            return dt.astimezone(_UTC).replace(tzinfo=None)
        return None

    # "today" — use specific time if present, else end-of-day
    if re.search(r"\btoday\b", lower):
        due = _apply_time(local_midnight, lower)
        if due == local_midnight:
            due = local_midnight + timedelta(hours=23, minutes=59)
        result = _future_utc(due)
        if result:
            return result

    # "tomorrow"
    if re.search(r"\btomorrow\b", lower):
        due = _apply_time(local_midnight + timedelta(days=1), lower)
        result = _future_utc(due)
        if result:
            return result

    # "in N days / weeks / months"
    m = _FUTURE_DAYS_RE.search(lower)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower().rstrip("s")
        if unit == "day":
            due = (now + timedelta(days=n)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif unit == "week":
            due = (now + timedelta(weeks=n)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # month
            due = (now + timedelta(days=n * 30)).replace(hour=0, minute=0, second=0, microsecond=0)
        result = _future_utc(due)
        if result:
            return result

    # "next week" → next Monday
    if re.search(r"\bnext\s+week\b", lower):
        days_ahead = (7 - local_midnight.weekday()) % 7 or 7
        due = local_midnight + timedelta(days=days_ahead)
        result = _future_utc(due)
        if result:
            return result

    # "next month" → 1st of next month
    if re.search(r"\bnext\s+month\b", lower):
        if local_midnight.month == 12:
            due = local_midnight.replace(year=local_midnight.year + 1, month=1, day=1)
        else:
            due = local_midnight.replace(month=local_midnight.month + 1, day=1)
        result = _future_utc(due)
        if result:
            return result

    # "next [weekday]" or "on [weekday]"
    wd_match = re.search(
        r"\b(?:next|on)\s+(" + "|".join(sorted(_WEEKDAY_MAP.keys(), key=len, reverse=True)) + r")\b",
        lower,
    )
    if wd_match:
        target_wd = _WEEKDAY_MAP[wd_match.group(1)]
        current_wd = local_midnight.weekday()
        delta = (target_wd - current_wd) % 7 or 7
        due = _apply_time(local_midnight + timedelta(days=delta), lower)
        result = _future_utc(due)
        if result:
            return result

    # "[Month] [Day]" e.g. "June 15" — this year if future, else next year
    mo_match = _MONTH_NAMES_RE.search(text)
    if mo_match:
        month_num = _MONTH_MAP.get(mo_match.group(1).lower(), 0)
        day_num = int(mo_match.group(2))
        if month_num and 1 <= day_num <= 31:
            try:
                due = local_midnight.replace(month=month_num, day=day_num)
            except ValueError:
                due = None
            if due is not None:
                if due <= now:
                    try:
                        due = due.replace(year=due.year + 1)
                    except ValueError:
                        due = None
                if due is not None:
                    result = _future_utc(due)
                    if result:
                        return result

    # ISO date "YYYY-MM-DD"
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_match:
        y, mth, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            due = datetime(y, mth, d, tzinfo=tz_obj)
            result = _future_utc(due)
            if result:
                return result
        except ValueError:
            pass

    return None
