import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateparser.search import search_dates

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
    r"\b(" + "|".join(sorted(_MONTH_MAP.keys(), key=len, reverse=True)) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b",
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


def _now_tuple(tz: str | None, now: datetime | None) -> tuple[ZoneInfo, datetime]:
    """Return (tz_obj, aware_now)."""
    if now is None:
        tz_obj = _resolve_tz(tz)
        now = datetime.now(tz_obj)
    elif now.tzinfo is not None:
        tz_obj = now.tzinfo
    else:
        tz_obj = _resolve_tz(tz)
        now = now.replace(tzinfo=tz_obj)
    return tz_obj, now


def _utc(dt: datetime) -> datetime:
    """Convert an aware datetime to naive UTC."""
    return dt.astimezone(_UTC).replace(tzinfo=None)


def _midnight(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


# dateparser.search sometimes hallucinates dates from random words (e.g. "me" → today).
# We reject any match whose substring contains no digits and no month name.
_DATE_SUBSTRING_RE = re.compile(
    r"\d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"january|february|march|april|june|july|august|september|october|november|december",
    re.IGNORECASE,
)


def _parse_dates(text: str, tz_str: str, now: datetime, *, prefer_future: bool = False) -> list[tuple[str, datetime]] | None:
    """Use dateparser to find all dates in text. Returns None if none found."""
    settings = {
        "TIMEZONE": tz_str,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future" if prefer_future else "current_period",
        "RELATIVE_BASE": now,
        "STRICT_PARSING": False,
    }
    try:
        results = search_dates(text, settings=settings)
    except Exception:
        return None
    if not results:
        return None
    # Filter out hallucinated matches (random words interpreted as dates).
    filtered = [r for r in results if _DATE_SUBSTRING_RE.search(r[0])]
    return filtered if filtered else None


def extract_range(text: str, tz: str | None = None, now: datetime | None = None) -> tuple[datetime, datetime, str] | None:
    """For created-at questions, return the [start, end) window (naive UTC) to filter
    `created_at` on, plus a human label. Returns None if the text isn't about time ranges.
    """
    tz_obj, now = _now_tuple(tz, now)
    local_midnight = _midnight(now)
    lower = text.strip().lower()

    # 1. App-specific relative words with custom semantics
    if re.search(r"\btoday\b", lower):
        return (_utc(local_midnight), _utc(now), "today")

    if re.search(r"\byesterday\b", lower):
        yesterday = local_midnight - timedelta(days=1)
        return (_utc(yesterday), _utc(local_midnight), "yesterday")

    if re.search(r"\bthis\s+week\b", lower):
        week_start = local_midnight - timedelta(days=local_midnight.weekday())
        return (_utc(week_start), _utc(now), "this week")

    m = _DAYS_RE.search(lower)
    if m:
        n = int(m.group(1))
        start = now - timedelta(days=n)
        return (_utc(start), _utc(now), f"the last {n} day{'s' if n != 1 else ''}")

    # 2. ISO exact-match (whole string)
    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text.strip())
    if iso_match:
        y, mth, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        start = datetime(y, mth, d, tzinfo=tz_obj)
        end = start + timedelta(days=1)
        return (_utc(start), _utc(end), f"on {text.strip()}")

    # 3. Weekday name (last occurrence) — checked before dateparser so we control
    #    the semantics (last Monday vs next Monday).
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
            return (_utc(start), _utc(end), f"on {w}")

    # 4. dateparser for exact calendar dates (e.g. "6th June", "June 15", "15/06/2024")
    parsed_list = _parse_dates(text, str(tz_obj), now, prefer_future=False)
    if parsed_list:
        if len(parsed_list) >= 2:
            # Range query like "from June 1 to June 15"
            _, dt1 = parsed_list[0]
            _, dt2 = parsed_list[1]
            start = _midnight(min(dt1, dt2))
            end = _midnight(max(dt1, dt2)) + timedelta(days=1)
            label = f"from {start.strftime('%B %d')} to {end.strftime('%B %d')}"
            return (_utc(start), _utc(end), label)
        _, dt = parsed_list[0]
        day_start = _midnight(dt)
        day_end = day_start + timedelta(days=1)
        label = f"on {day_start.strftime('%B %d, %Y')}"
        return (_utc(day_start), _utc(day_end), label)

    return None


def extract_due_range(
    text: str, tz: str | None = None, now: datetime | None = None
) -> tuple[datetime, datetime, str] | None:
    """For due-date questions, return the [start, end) window (naive UTC) to filter
    `due_at` on, plus a human label. Returns None if the text isn't about due dates.
    """
    if not _DUE_INTENT_RE.search(text):
        return None
    # "what tasks did I save this week?" has planning vocab but is asking about
    # creation time, not due time.  Creation-time words override the due intent.
    if _CREATION_INTENT_RE.search(text):
        return None

    tz_obj, now = _now_tuple(tz, now)
    local_midnight = _midnight(now)
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
        # Try dateparser for exact due dates (e.g. "what's due on 6th June?")
        parsed_list = _parse_dates(text, str(tz_obj), now, prefer_future=True)
        if parsed_list:
            _, dt = parsed_list[0]
            start = _midnight(dt)
            end = start + timedelta(days=1)
            label = f"on {start.strftime('%B %d, %Y')}"
            return (_utc(start), _utc(end), label)

        # Generic "what's due / what do I have to do" → overdue + the next 7 days.
        start, end, label = far_past, local_midnight + timedelta(days=8), "soon"

    start_utc = _utc(start)
    end_utc = _utc(end)
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
    tz_obj, now = _now_tuple(tz, now)
    local_midnight = _midnight(now)
    lower = text.lower()

    def _future_utc(dt: datetime) -> datetime | None:
        if dt > now:
            return _utc(dt)
        return None

    # 1. "today" — use specific time if present, else end-of-day
    if re.search(r"\btoday\b", lower):
        due = _apply_time(local_midnight, lower)
        if due == local_midnight:
            due = local_midnight + timedelta(hours=23, minutes=59)
        result = _future_utc(due)
        if result:
            return result

    # 2. "tomorrow"
    if re.search(r"\btomorrow\b", lower):
        due = _apply_time(local_midnight + timedelta(days=1), lower)
        result = _future_utc(due)
        if result:
            return result

    # 3. "in N days / weeks / months"
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

    # 4. "next week" → next Monday
    if re.search(r"\bnext\s+week\b", lower):
        days_ahead = (7 - local_midnight.weekday()) % 7 or 7
        due = local_midnight + timedelta(days=days_ahead)
        result = _future_utc(due)
        if result:
            return result

    # 5. "next month" → 1st of next month
    if re.search(r"\bnext\s+month\b", lower):
        if local_midnight.month == 12:
            due = local_midnight.replace(year=local_midnight.year + 1, month=1, day=1)
        else:
            due = local_midnight.replace(month=local_midnight.month + 1, day=1)
        result = _future_utc(due)
        if result:
            return result

    # 6. "next [weekday]" or "on [weekday]"
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

    # 7. dateparser for exact calendar dates (e.g. "6th June", "June 15", "15/06/2024")
    parsed_list = _parse_dates(text, str(tz_obj), now, prefer_future=True)
    if parsed_list:
        _, dt = parsed_list[0]
        due = _apply_time(dt, lower)
        result = _future_utc(due)
        if result:
            return result

    # 8. "[Month] [Day]" e.g. "June 15" — this year if future, else next year
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
                due = _apply_time(due, lower)
                if due <= now:
                    try:
                        due = due.replace(year=due.year + 1)
                    except ValueError:
                        due = None
                if due is not None:
                    result = _future_utc(due)
                    if result:
                        return result

    # 9. ISO date "YYYY-MM-DD"
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
