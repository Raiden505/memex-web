"""Tests for recall/router.py heuristic paths.

All tests that exercise the heuristic paths do NOT require a real Config or
Gemini API key — the heuristic returns before calling classify_intent.
Tests that would fall through to classify_intent mock recall.router.classify_intent
(NOT recall.llm.classify_intent, because router imports classify_intent by name
at module load time).
"""

from unittest.mock import patch

import pytest

from recall.router import route

# Correct patch target: the name 'classify_intent' in the recall.router module namespace.
_PATCH = "recall.router.classify_intent"


# ---------------------------------------------------------------------------
# Greeting / meta → "general"  (no LLM call)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "hi",
    "hello",
    "Hey",
    "yo",
    "sup",
    "hiya",
    "howdy",
    "thanks",
    "thank you",
    "thx",
    "ty",
    "ok",
    "okay",
    "cool",
    "nice",
    "good morning",
    "good evening",
    "good afternoon",
    "gm",
    "help",
    "what can you do",
    "what can you do?",
    "who are you",
    "who are you?",
])
def test_greetings_and_meta_are_general(text):
    with patch(_PATCH) as mock:
        result = route(text, None)
        assert result == "general", f"Expected 'general' for {text!r}, got {result!r}"
        mock.assert_not_called()


# ---------------------------------------------------------------------------
# Forget prefixes → "forget"  (no LLM call)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "forget the dentist appointment",
    "forget what I said about Ahmed",
    "forget everything",
    "forget it all",
    "delete the note about coffee",
    "delete all my memories",
    "remove that thing I said",
    "remove all my notes",
    "forget what i said",
    "forget what I told you about the trip",
    "delete the memory of the meeting",
    "delete the memory about the dentist",
])
def test_forget_prefixes_route_to_forget(text):
    with patch(_PATCH) as mock:
        result = route(text, None)
        assert result == "forget", f"Expected 'forget' for {text!r}, got {result!r}"
        mock.assert_not_called()


# ---------------------------------------------------------------------------
# Query-starter words → "query"  (no LLM call)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "what did I tell you about Ahmed?",
    "what's my dentist's name?",
    "where did I park?",
    "when is the meeting?",
    "who told me about the jackets?",
    "why did I write that note?",
    "how do I fix this?",
    "which file did I mention?",
    "whats the password for the wifi?",
])
def test_query_starter_words_route_to_query(text):
    with patch(_PATCH) as mock:
        result = route(text, None)
        assert result == "query", f"Expected 'query' for {text!r}, got {result!r}"
        mock.assert_not_called()


# ---------------------------------------------------------------------------
# "did I / do I / have I" prefixes → "query"  (no LLM call)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "did I remember to call mom?",
    "did I note anything about Monday?",
    "do I have the dentist's number?",
    "do I know Ahmed's email?",
    "have I noted the meeting time?",
    "have I saved anything about the project?",
])
def test_query_prefixes_route_to_query(text):
    with patch(_PATCH) as mock:
        result = route(text, None)
        assert result == "query", f"Expected 'query' for {text!r}, got {result!r}"
        mock.assert_not_called()


# ---------------------------------------------------------------------------
# Ambiguous inputs → call classify_intent
# ---------------------------------------------------------------------------

def test_bare_statement_calls_classifier():
    with patch(_PATCH, return_value="store") as mock:
        result = route("my friend Ahmed is tall", None)
        assert result == "store"
        mock.assert_called_once()


def test_question_without_starter_calls_classifier():
    # "Is the meeting tomorrow?" — starts with "Is" which is not a query starter
    with patch(_PATCH, return_value="query") as mock:
        result = route("Is the meeting tomorrow?", None)
        assert result == "query"
        mock.assert_called_once()


def test_remind_me_calls_classifier():
    # "remind me" is ambiguous — LLM decides STORE vs QUERY
    with patch(_PATCH, return_value="store") as mock:
        result = route("remind me to call mom", None)
        assert result == "store"
        mock.assert_called_once()


def test_remind_me_where_calls_classifier():
    # "remind me where I parked" — starts with "remind", not a query starter
    with patch(_PATCH, return_value="query") as mock:
        result = route("remind me where I parked", None)
        assert result == "query"
        mock.assert_called_once()


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------

def test_uppercase_greeting():
    with patch(_PATCH) as mock:
        assert route("HELLO", None) == "general"
        mock.assert_not_called()


def test_mixed_case_forget():
    with patch(_PATCH) as mock:
        assert route("Forget the dentist note", None) == "forget"
        mock.assert_not_called()


def test_mixed_case_query_starter():
    with patch(_PATCH) as mock:
        assert route("What did I save today?", None) == "query"
        mock.assert_not_called()


# ---------------------------------------------------------------------------
# Classifier fallback (classify_intent handles its own exceptions internally)
# ---------------------------------------------------------------------------

def test_classify_intent_returning_store_propagates():
    with patch(_PATCH, return_value="store") as mock:
        result = route("some unknown statement", None)
        assert result == "store"
        mock.assert_called_once()


def test_classify_intent_returning_query_propagates():
    with patch(_PATCH, return_value="query") as mock:
        result = route("did it work out?", None)
        # "did" starts "did i" prefix → caught by heuristic before classifier
        # so mock will NOT be called — this tests an ambiguous non-prefix form
        # Actually "did it" doesn't match "did i " prefix → falls through to classifier
        assert result == "query"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_whitespace_only_falls_through():
    # "   ".strip().lower() == "" → no heuristic matches → classifier called
    with patch(_PATCH, return_value="store") as mock:
        route("   ", None)
        mock.assert_called_once()


def test_single_word_non_greeting_calls_classifier():
    with patch(_PATCH, return_value="store") as mock:
        route("coffee", None)
        mock.assert_called_once()


# ---------------------------------------------------------------------------
# Quick win: conversation-history follow-up routing
# ---------------------------------------------------------------------------

def test_follow_up_short_phrase_routes_to_query():
    # After a query, a short bare phrase like "his email" should be a follow-up.
    history = [{"role": "assistant", "content": "Ahmed is your dentist."}]
    with patch(_PATCH) as mock:
        result = route("his email", None, history=history)
        assert result == "query"
        mock.assert_not_called()


def test_follow_up_pronoun_starter_routes_to_query():
    history = [{"role": "assistant", "content": "You saved a note about the meeting."}]
    with patch(_PATCH) as mock:
        assert route("what about the dentist?", None, history=history) == "query"
        assert route("when was that?", None, history=history) == "query"
        assert route("how do I get there?", None, history=history) == "query"
        mock.assert_not_called()


def test_follow_up_preposition_starter_routes_to_query():
    history = [{"role": "assistant", "content": "The report is due Friday."}]
    with patch(_PATCH) as mock:
        assert route("on what date?", None, history=history) == "query"
        assert route("for which client?", None, history=history) == "query"
        mock.assert_not_called()


def test_no_history_falls_through_to_classifier():
    with patch(_PATCH, return_value="store") as mock:
        route("his email", None, history=None)
        mock.assert_called_once()


def test_last_turn_was_user_not_assistant_falls_through():
    # If the last entry is a user message, this is NOT a follow-up to an assistant reply.
    history = [{"role": "user", "content": "What did I save?"}]
    with patch(_PATCH, return_value="store") as mock:
        route("his email", None, history=history)
        mock.assert_called_once()


def test_long_statement_after_assistant_falls_through():
    # A long statement after an assistant reply is probably a new topic, not a follow-up.
    history = [{"role": "assistant", "content": "You saved a note about the meeting."}]
    with patch(_PATCH, return_value="store") as mock:
        route("I need to remember to buy groceries after work and call my mom", None, history=history)
        mock.assert_called_once()
