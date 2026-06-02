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


def route(text: str, cfg: Config) -> Intent:
    normalized = text.strip().lower()

    if normalized in _GREETINGS or normalized in _META:
        return "general"

    first_word = normalized.split()[0] if normalized.split() else ""
    if first_word in _QUERY_STARTERS:
        return "query"
    if any(normalized.startswith(p) for p in _QUERY_PREFIXES):
        return "query"

    return classify_intent(text, cfg)
