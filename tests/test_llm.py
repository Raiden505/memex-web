"""Tests for recall/llm.py (network-free portions only).

_filter_relevant and save_ack do not require a Gemini API key.
"""

import pytest
from recall.llm import _filter_relevant, save_ack
from recall.models import SearchResult
from recall.prompts import SAVE_ACKS


def _sr(similarity: float, content: str = "test") -> SearchResult:
    return SearchResult(
        id="00000000-0000-0000-0000-000000000001",
        content=content,
        created_at="2024-06-05T10:00:00",
        similarity=similarity,
    )


# ---------------------------------------------------------------------------
# _filter_relevant
# ---------------------------------------------------------------------------

class TestFilterRelevant:
    def test_empty_list(self):
        assert _filter_relevant([]) == []

    def test_single_high_similarity(self):
        items = [_sr(0.9)]
        result = _filter_relevant(items)
        assert len(result) == 1

    def test_single_below_floor_is_filtered_out(self):
        # Similarity 0.1 < floor (0.2) → filtered even if it's the only item.
        # This upholds the no-hallucination guarantee: an answer from a
        # weakly-related memory is worse than "nothing saved about that."
        items = [_sr(0.1)]
        result = _filter_relevant(items)
        assert len(result) == 0

    def test_single_at_floor_is_kept(self):
        items = [_sr(0.2)]
        result = _filter_relevant(items)
        assert len(result) == 1

    def test_single_above_floor_is_kept(self):
        items = [_sr(0.5)]
        result = _filter_relevant(items)
        assert len(result) == 1

    def test_two_close_similarities_both_kept(self):
        items = [_sr(0.8), _sr(0.7)]
        result = _filter_relevant(items)
        assert len(result) == 2

    def test_wide_spread_drops_weak_item(self):
        # top=0.9, spread=0.2 → cutoff=0.7; item at 0.5 is dropped
        items = [_sr(0.9), _sr(0.5)]
        result = _filter_relevant(items)
        assert len(result) == 1
        assert result[0].similarity == 0.9

    def test_floor_applies_when_top_is_low(self):
        # top=0.15, floor=0.20 → cutoff=max(0.20, 0.15-0.20)=0.20
        # Only item at 0.15 < 0.20 → filtered out (empty)
        items = [_sr(0.15)]
        result = _filter_relevant(items)
        # 0.15 < max(0.2, 0.15-0.2) = max(0.2, -0.05) = 0.2 → dropped
        assert len(result) == 0

    def test_floor_keeps_item_at_exactly_floor(self):
        # similarity == 0.20 == floor → kept
        items = [_sr(0.20)]
        result = _filter_relevant(items)
        assert len(result) == 1

    def test_multiple_items_mixed(self):
        items = [_sr(0.85), _sr(0.80), _sr(0.75), _sr(0.40), _sr(0.10)]
        result = _filter_relevant(items)
        # top=0.85, spread=0.20 → cutoff=max(0.20, 0.65)=0.65
        # 0.85 ✓, 0.80 ✓, 0.75 ✓, 0.40 ✗, 0.10 ✗
        assert len(result) == 3
        assert all(r.similarity >= 0.65 for r in result)

    def test_all_items_above_floor_but_spread_filters_some(self):
        items = [_sr(0.9), _sr(0.8), _sr(0.6), _sr(0.5)]
        result = _filter_relevant(items)
        # top=0.9, cutoff=max(0.2, 0.7)=0.7
        # 0.9 ✓, 0.8 ✓, 0.6 ✗, 0.5 ✗
        assert len(result) == 2

    def test_preserves_order(self):
        # Results should remain in input order (descending similarity)
        items = [_sr(0.9, "first"), _sr(0.85, "second"), _sr(0.8, "third")]
        result = _filter_relevant(items)
        assert [r.content for r in result] == ["first", "second", "third"]

    def test_all_zero_similarity(self):
        items = [_sr(0.0), _sr(0.0), _sr(0.0)]
        # top=0.0, cutoff=max(0.2, 0.0-0.2)=0.2; all 0.0 < 0.2 → filtered
        result = _filter_relevant(items)
        assert len(result) == 0

    def test_all_identical_high_similarity(self):
        items = [_sr(0.85)] * 5
        result = _filter_relevant(items)
        # top=0.85, cutoff=max(0.2, 0.65)=0.65; all 0.85 >= 0.65 → kept
        assert len(result) == 5


# ---------------------------------------------------------------------------
# save_ack
# ---------------------------------------------------------------------------

class TestSaveAck:
    def test_returns_string(self):
        assert isinstance(save_ack(), str)

    def test_returns_from_ack_pool(self):
        ack = save_ack()
        assert ack in SAVE_ACKS

    def test_injectable_rng_deterministic(self):
        import random
        rng = random.Random(42)
        a1 = save_ack(rng=rng)
        rng2 = random.Random(42)
        a2 = save_ack(rng=rng2)
        assert a1 == a2

    def test_all_acks_are_strings(self):
        for ack in SAVE_ACKS:
            assert isinstance(ack, str)
            assert len(ack) > 0


# ---------------------------------------------------------------------------
# _is_answer_grounded (quick-win self-verification)
# ---------------------------------------------------------------------------

from recall.llm import _is_answer_grounded


class TestIsAnswerGrounded:
    def test_vacuously_true_when_no_memories(self):
        assert _is_answer_grounded("anything", []) is True

    def test_vacuously_true_when_empty_answer(self):
        assert _is_answer_grounded("", ["hello world"]) is True

    def test_grounded_when_shared_word_present(self):
        memories = ["Ahmed's email is ahmed@example.com"]
        assert _is_answer_grounded("His email is ahmed@example.com", memories) is True

    def test_ungrounded_when_no_shared_substantive_words(self):
        memories = ["The sky is blue today"]
        assert _is_answer_grounded("Quantum mechanics is fascinating.", memories) is False

    def test_grounded_by_long_substring_quote(self):
        memories = ["Meeting rescheduled to 3pm on Thursday"]
        assert _is_answer_grounded("Sure, the meeting rescheduled to 3pm on Thursday works.", memories) is True

    def test_ungrounded_on_generic_polite_response(self):
        memories = ["Buy milk and eggs"]
        assert _is_answer_grounded("You're welcome! Let me know if you need anything else.", memories) is False

    def test_grounded_by_short_but_relevant_answer(self):
        memories = ["Dentist phone: 555-0199"]
        assert _is_answer_grounded("555-0199", memories) is True
