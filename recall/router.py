from recall.config import Config
from recall.llm import classify_intent
from recall.models import Intent

_QUERY_STARTERS = {"what", "whats", "what's", "where", "when", "who", "why", "how", "which"}
_QUERY_PREFIXES = ("did i ", "do i ", "have i ")

_GREETINGS = {
    "hi", "hello", "hey", "yo", "sup", "hiya", "howdy",
    "thanks", "thank you", "thx", "ty", "ok", "okay", "cool", "nice",
    "good morning", "good evening", "good afternoon", "gm",
}
_META = {"help", "what can you do", "what can you do?", "who are you", "who are you?"}

_FORGET_PREFIXES = ("forget ", "delete ", "remove ")
_FORGET_PHRASES = (
    "forget what i", "forget everything", "forget it all",
    "delete the memory", "delete all my", "remove all my",
)

# Quick win: pronouns, prepositions and short words that signal a follow-up to
# a previous query (e.g. "his email", "when was that", "what about the dentist").
_FOLLOW_UP_STARTERS = {
    "his", "her", "its", "the", "that", "this", "what", "how", "when",
    "where", "who", "why", "which", "is", "are", "was", "were", "did",
    "do", "does", "can", "could", "would", "should", "will", "about",
    "and", "or", "but", "on", "at", "in", "for", "with", "by", "from",
    "to", "of", "so", "then", "also", "plus", "next", "and", "or",
}


def _is_follow_up(text: str, history: list[dict]) -> bool:
    """Heuristic: if the assistant just answered and the user sends a short
    reference-heavy phrase, treat it as a query follow-up."""
    if not history:
        return False
    # We only care if the most recent history entry is from the assistant,
    # meaning the user is responding to a reply we just gave.
    last = history[-1]
    if last.get("role") != "assistant":
        return False

    normalized = text.strip().lower()
    words = normalized.split()
    word_count = len(words)

    # Very short bare phrases are almost always follow-ups
    if word_count <= 4:
        return True

    # Starts with a known follow-up word (pronoun, preposition, question word)
    if words and words[0] in _FOLLOW_UP_STARTERS:
        return True

    # Ends with a question mark on a short sentence
    if normalized.endswith("?") and word_count <= 8:
        return True

    return False


def route(text: str, cfg: Config, history: list[dict] | None = None) -> Intent:
    normalized = text.strip().lower()

    if normalized in _GREETINGS or normalized in _META:
        return "general"

    # Quick-win follow-up routing: don't burn an LLM call on obvious continuations.
    if history is not None and _is_follow_up(text, history):
        return "query"

    # Forget heuristic — before query so "delete X" never misroutes to query
    if any(normalized.startswith(p) for p in _FORGET_PREFIXES):
        return "forget"
    if any(phrase in normalized for phrase in _FORGET_PHRASES):
        return "forget"

    first_word = normalized.split()[0] if normalized.split() else ""
    if first_word in _QUERY_STARTERS:
        return "query"
    if any(normalized.startswith(p) for p in _QUERY_PREFIXES):
        return "query"

    return classify_intent(text, cfg)
