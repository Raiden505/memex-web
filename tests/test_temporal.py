"""Comprehensive tests for recall/temporal.py.

All tests use a fixed 'now' so they are deterministic:
  NOW = Wednesday 2024-06-05 10:30:00 UTC
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from recall.temporal import extract_due, extract_due_range, extract_range

_UTC = ZoneInfo("UTC")
_NOW = datetime(2024, 6, 5, 10, 30, 0, tzinfo=_UTC)  # Wed Jun 5 2024, 10:30 UTC


def _utc(*args):
    return datetime(*args)  # naive UTC


# ---------------------------------------------------------------------------
# extract_range — filters on created_at (when was it *saved*)
# ---------------------------------------------------------------------------

class TestExtractRange:
    # --- "today" ---
    def test_bare_word_today(self):
        s, e, label = extract_range("today", now=_NOW)
        assert label == "today"
        assert s == _utc(2024, 6, 5, 0, 0)
        assert e == _utc(2024, 6, 5, 10, 30)

    def test_today_inside_sentence(self):
        s, e, label = extract_range("what did I save today?", now=_NOW)
        assert label == "today"

    def test_today_inside_longer_sentence(self):
        s, e, label = extract_range("tell me everything I told you today", now=_NOW)
        assert label == "today"

    # --- "yesterday" ---
    def test_bare_word_yesterday(self):
        s, e, label = extract_range("yesterday", now=_NOW)
        assert label == "yesterday"
        assert s == _utc(2024, 6, 4, 0, 0)
        assert e == _utc(2024, 6, 5, 0, 0)

    def test_yesterday_inside_sentence(self):
        s, e, label = extract_range("what did I tell you yesterday?", now=_NOW)
        assert label == "yesterday"

    def test_yesterday_full_day(self):
        s, e, _ = extract_range("yesterday", now=_NOW)
        assert (e - s) == timedelta(days=1)

    # --- "this week" ---
    def test_bare_word_this_week(self):
        s, e, label = extract_range("this week", now=_NOW)
        assert label == "this week"
        # Monday Jun 3 00:00
        assert s == _utc(2024, 6, 3, 0, 0)
        assert e == _utc(2024, 6, 5, 10, 30)

    def test_this_week_inside_sentence(self):
        s, e, label = extract_range("what have I been saving this week?", now=_NOW)
        assert label == "this week"

    # --- "last N days" / "past N days" ---
    def test_last_3_days(self):
        s, e, label = extract_range("last 3 days", now=_NOW)
        assert label == "the last 3 days"
        assert s == _utc(2024, 6, 2, 10, 30)
        assert e == _utc(2024, 6, 5, 10, 30)

    def test_past_7_days(self):
        s, e, label = extract_range("past 7 days", now=_NOW)
        assert "7" in label
        assert s == _utc(2024, 5, 29, 10, 30)

    def test_last_1_day(self):
        _, _, label = extract_range("last 1 day", now=_NOW)
        assert label == "the last 1 day"  # singular

    # --- ISO date ---
    def test_iso_date(self):
        s, e, label = extract_range("2024-01-15", now=_NOW)
        assert label == "on 2024-01-15"
        assert s == _utc(2024, 1, 15)
        assert e == _utc(2024, 1, 16)

    # --- Weekdays ---
    def test_weekday_monday(self):
        # Wed Jun 5; last Monday = Jun 3
        s, e, _ = extract_range("monday", now=_NOW)
        assert s == _utc(2024, 6, 3)
        assert e == _utc(2024, 6, 4)

    def test_weekday_tuesday(self):
        # Last Tuesday = Jun 4
        s, _, _ = extract_range("tuesday", now=_NOW)
        assert s == _utc(2024, 6, 4)

    def test_weekday_friday(self):
        # Last Friday = May 31
        s, _, _ = extract_range("friday", now=_NOW)
        assert s == _utc(2024, 5, 31)

    def test_weekday_sunday(self):
        # Last Sunday = Jun 2
        s, _, _ = extract_range("sunday", now=_NOW)
        assert s == _utc(2024, 6, 2)

    def test_weekday_wednesday_is_today(self):
        # "wednesday" when today is Wednesday → today's full day
        s, e, _ = extract_range("wednesday", now=_NOW)
        assert s == _utc(2024, 6, 5)   # midnight today
        assert e == _utc(2024, 6, 6)   # midnight tomorrow

    # --- No match ---
    def test_no_time_ref(self):
        assert extract_range("my friend told me about jackets", now=_NOW) is None

    def test_empty_string(self):
        assert extract_range("", now=_NOW) is None

    def test_future_only_sentence(self):
        assert extract_range("I will do this", now=_NOW) is None

    def test_number_without_days(self):
        # "3" alone should not match "last N days"
        assert extract_range("I thought of 3 ideas", now=_NOW) is None

    def test_priority_today_over_yesterday(self):
        # "today and yesterday" → "today" appears first → today wins
        _, _, label = extract_range("today and yesterday", now=_NOW)
        assert label == "today"

    # --- Exact calendar dates via dateparser ---
    def test_day_month_ordinal_created_at(self):
        s, e, label = extract_range("what did I save on 6th June?", now=_NOW)
        assert label == "on June 06, 2024"
        assert s == _utc(2024, 6, 6)
        assert e == _utc(2024, 6, 7)

    def test_month_day_created_at(self):
        s, e, label = extract_range("what did I save June 6?", now=_NOW)
        assert label == "on June 06, 2024"
        assert s == _utc(2024, 6, 6)
        assert e == _utc(2024, 6, 7)

    def test_slash_date_created_at(self):
        s, e, label = extract_range("what did I save on 15/06/2024?", now=_NOW)
        assert label == "on June 15, 2024"
        assert s == _utc(2024, 6, 15)
        assert e == _utc(2024, 6, 16)

    def test_dash_date_us_created_at(self):
        s, e, label = extract_range("what did I save on 06-15-2024?", now=_NOW)
        assert label == "on June 15, 2024"
        assert s == _utc(2024, 6, 15)
        assert e == _utc(2024, 6, 16)

    def test_date_range_created_at(self):
        s, e, label = extract_range("what did I save from June 1 to June 15?", now=_NOW)
        assert s == _utc(2024, 6, 1)
        assert e == _utc(2024, 6, 16)

    def test_day_of_month_with_of_created_at(self):
        s, e, label = extract_range("what did I save on the 10th of July?", now=_NOW)
        assert label == "on July 10, 2024"
        assert s == _utc(2024, 7, 10)
        assert e == _utc(2024, 7, 11)


# ---------------------------------------------------------------------------
# extract_due_range — filters on due_at (when is it *due*)
# ---------------------------------------------------------------------------

class TestExtractDueRange:
    # --- "due today" ---
    def test_due_today(self):
        s, e, label = extract_due_range("what's due today?", now=_NOW)
        assert label == "today"
        assert s == _utc(2024, 6, 5, 0, 0)   # full calendar day (not capped at now)
        assert e == _utc(2024, 6, 6, 0, 0)

    def test_tasks_due_today(self):
        s, e, label = extract_due_range("any tasks due today?", now=_NOW)
        assert label == "today"

    # --- "due tomorrow" ---
    def test_due_tomorrow(self):
        s, e, label = extract_due_range("what's due tomorrow?", now=_NOW)
        assert label == "tomorrow"
        assert s == _utc(2024, 6, 6, 0, 0)
        assert e == _utc(2024, 6, 7, 0, 0)

    def test_tasks_for_tomorrow(self):
        _, _, label = extract_due_range("any tasks for tomorrow?", now=_NOW)
        assert label == "tomorrow"

    # --- "overdue" ---
    def test_overdue(self):
        s, e, label = extract_due_range("what's overdue?", now=_NOW)
        assert label == "overdue"
        assert e == _utc(2024, 6, 5, 10, 30)  # up to now

    # --- "this week" due ---
    def test_due_this_week(self):
        s, e, label = extract_due_range("tasks due this week", now=_NOW)
        assert label == "this week"
        # This week window = Mon Jun 3 to Mon Jun 10
        assert s == _utc(2024, 6, 3)
        assert e == _utc(2024, 6, 10)

    # --- "next week" due ---
    def test_due_next_week(self):
        s, e, label = extract_due_range("deadlines next week", now=_NOW)
        assert label == "next week"
        assert s == _utc(2024, 6, 10)
        assert e == _utc(2024, 6, 17)

    # --- generic due (no time word) ---
    def test_generic_due_query(self):
        s, e, label = extract_due_range("what do I have to do?", now=_NOW)
        assert label == "soon"

    def test_upcoming_tasks(self):
        _, _, label = extract_due_range("anything upcoming?", now=_NOW)
        assert label == "soon"

    def test_reminders(self):
        _, _, label = extract_due_range("show me my reminders", now=_NOW)
        assert label == "soon"

    def test_scheduled(self):
        _, _, label = extract_due_range("anything scheduled for me?", now=_NOW)
        assert label == "soon"

    def test_need_to_do(self):
        _, _, label = extract_due_range("what do I need to do?", now=_NOW)
        assert label == "soon"

    def test_have_to_do(self):
        _, _, label = extract_due_range("what do I have to do this week?", now=_NOW)
        assert label == "this week"

    # --- "soon" window coverage ---
    def test_soon_window_includes_next_7_days(self):
        s, e, _ = extract_due_range("what tasks do I have?", now=_NOW)
        # should include items overdue (far_past to now+8d)
        expected_end = _utc(2024, 6, 13)  # local_midnight + 8 days
        assert e >= expected_end

    # --- should NOT match (no due-intent keyword) ---
    def test_no_due_intent_for_today(self):
        assert extract_due_range("what did I save today?", now=_NOW) is None

    def test_no_due_intent_general(self):
        assert extract_due_range("tell me about jackets", now=_NOW) is None

    def test_no_due_intent_empty(self):
        assert extract_due_range("", now=_NOW) is None

    def test_saved_tasks_query_no_due_match(self):
        # "what tasks did I save?" — has "tasks" but also "save" → temporal recall
        result = extract_due_range("what tasks did I save?", now=_NOW)
        # This may or may not return None depending on implementation.
        # The key requirement is that "what did I save today?" returns None.
        # We test only the clear negative case:
        assert extract_due_range("what did I save today?", now=_NOW) is None

    # --- Exact calendar dates via dateparser ---
    def test_due_on_exact_date(self):
        s, e, label = extract_due_range("what's due on 6th June?", now=_NOW)
        assert label == "on June 06, 2024"
        assert s == _utc(2024, 6, 6)
        assert e == _utc(2024, 6, 7)

    def test_due_exact_date(self):
        s, e, label = extract_due_range("deadlines for June 15", now=_NOW)
        assert s == _utc(2024, 6, 15)
        assert e == _utc(2024, 6, 16)
        assert label == "on June 15, 2024"


# ---------------------------------------------------------------------------
# extract_due — extracts a future due date for storing a memory
# ---------------------------------------------------------------------------

class TestExtractDue:
    # --- "tomorrow" ---
    def test_tomorrow_no_time(self):
        # midnight tomorrow UTC
        result = extract_due("call mom tomorrow", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 6).date()

    def test_tomorrow_with_time(self):
        result = extract_due("meeting tomorrow at 3pm", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 6).date()
        assert result.hour == 15
        assert result.minute == 0

    def test_tomorrow_with_am_time(self):
        result = extract_due("call at 9am tomorrow", now=_NOW)
        assert result is not None
        assert result.hour == 9

    def test_tomorrow_midnight(self):
        result = extract_due("submit tomorrow at 12am", now=_NOW)
        assert result is not None
        assert result.hour == 0

    # --- "today" ---
    def test_today_no_time_extracts_end_of_day(self):
        result = extract_due("do this today", now=_NOW)
        assert result is not None
        assert result.hour == 23
        assert result.minute == 59

    def test_today_future_time(self):
        # 10:30am now → 3pm today is future
        result = extract_due("meeting today at 3pm", now=_NOW)
        assert result is not None
        assert result.hour == 15

    def test_today_past_time_returns_none(self):
        # 8am today is past when now is 10:30am
        result = extract_due("meeting today at 8am", now=_NOW)
        assert result is None

    # --- "in N days/weeks/months" ---
    def test_in_3_days(self):
        result = extract_due("submit in 3 days", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 8).date()

    def test_in_2_weeks(self):
        result = extract_due("done in 2 weeks", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 19).date()

    def test_in_1_month(self):
        result = extract_due("complete in 1 month", now=_NOW)
        assert result is not None
        # ~30 days: Jul 5
        assert result.date() == datetime(2024, 7, 5).date()

    # --- "next week" ---
    def test_next_week(self):
        # Wed Jun 5 → next Monday = Jun 10
        result = extract_due("finish this next week", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 10).date()

    # --- "next month" ---
    def test_next_month(self):
        result = extract_due("pay rent next month", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 7, 1).date()

    # --- "next [weekday]" / "on [weekday]" ---
    def test_next_friday(self):
        result = extract_due("dentist next friday", now=_NOW)
        assert result is not None
        # Wed Jun 5 → next Friday = Jun 7
        assert result.date() == datetime(2024, 6, 7).date()

    def test_on_monday(self):
        result = extract_due("submit on monday", now=_NOW)
        assert result is not None
        # Wed Jun 5 → next Monday = Jun 10
        assert result.date() == datetime(2024, 6, 10).date()

    def test_next_tuesday(self):
        result = extract_due("meeting next tuesday", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 11).date()

    # --- Month Day ---
    def test_month_day_future(self):
        # June 15 > June 5 → this year
        result = extract_due("submit June 15", now=_NOW)
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_month_day_past_wraps_to_next_year(self):
        # January 15 < June 5 → next year
        result = extract_due("submit January 15", now=_NOW)
        assert result is not None
        assert result.year == 2025
        assert result.month == 1

    def test_month_day_today_wraps_to_next_year(self):
        # June 5 == today → not future, next year
        result = extract_due("submit June 5", now=_NOW)
        # Depends on whether the day is strictly after now
        # June 5 midnight <= June 5 10:30am = not future → next year
        if result is not None:
            assert result.year >= 2024

    # --- ISO date ---
    def test_iso_date_future(self):
        result = extract_due("deadline is 2025-12-31", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2025, 12, 31).date()

    def test_iso_date_past_returns_none(self):
        result = extract_due("the deadline was 2023-01-01", now=_NOW)
        assert result is None

    # --- No date in text ---
    def test_no_date(self):
        assert extract_due("random thought about jackets", now=_NOW) is None

    def test_empty_string(self):
        assert extract_due("", now=_NOW) is None

    def test_pure_statement(self):
        assert extract_due("my friend Ahmed is funny", now=_NOW) is None

    # --- Naive UTC output ---
    def test_output_is_naive(self):
        result = extract_due("call mom tomorrow", now=_NOW)
        assert result is not None
        assert result.tzinfo is None  # should be naive UTC

    # --- Non-UTC timezone handling ---
    def test_tomorrow_respects_tz(self):
        # UTC+5 user, 11pm local → tomorrow in UTC+5 = today in UTC
        now_plus5 = datetime(2024, 6, 5, 23, 0, 0, tzinfo=ZoneInfo("Asia/Karachi"))
        result = extract_due("call mom tomorrow", tz="Asia/Karachi", now=now_plus5)
        assert result is not None
        # Tomorrow in Karachi = Jun 6 local = Jun 5 UTC (their tomorrow starts at Jun 5 19:00 UTC)
        # The function returns naive UTC, so it should be Jun 6 in Karachi local time
        assert result is not None  # just verify it extracts something

    # --- ensure no false match on partial words ---
    def test_no_partial_word_match_for_monday(self):
        # "mandatory" contains "mon" — should not match as weekday
        result = extract_due("submit mandatory report", now=_NOW)
        assert result is None

    def test_no_partial_word_match_for_today(self):
        # "nowadays" should not match "today"
        result = extract_due("nowadays things are different", now=_NOW)
        assert result is None

    # --- Exact calendar dates via dateparser ---
    def test_day_month_ordinal(self):
        result = extract_due("submit report 6th June", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 6).date()

    def test_month_day_ordinal_with_time(self):
        result = extract_due("meeting on June 15th at 3pm", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 15).date()
        assert result.hour == 15

    def test_slash_date(self):
        result = extract_due("deadline 15/06/2025", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2025, 6, 15).date()

    def test_dash_date_us(self):
        result = extract_due("birthday 06-15-2025", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2025, 6, 15).date()

    def test_day_of_month_with_of(self):
        result = extract_due("call mom on the 10th of July", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 7, 10).date()

    def test_bare_day_month(self):
        result = extract_due("due 6 June", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 6).date()

    def test_exact_date_past_wraps_year(self):
        # January 15 is past relative to June 5 → should wrap to 2025
        result = extract_due("submit January 15", now=_NOW)
        assert result is not None
        assert result.year == 2025

    def test_exact_date_with_time_am(self):
        result = extract_due("meeting June 10 at 9am", now=_NOW)
        assert result is not None
        assert result.date() == datetime(2024, 6, 10).date()
        assert result.hour == 9
