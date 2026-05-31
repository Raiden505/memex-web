from recall.config import Config
from recall.llm import classify_intent
from recall.models import Intent

_QUERY_STARTERS = {"what", "whats", "what's", "where", "when", "who", "why", "how", "which"}
_QUERY_PREFIXES = ("did i ", "do i ", "have i ")


def route(text: str, cfg: Config) -> Intent:
    normalized = text.strip().lower()

    # Fast heuristic — no LLM call needed for obvious cases
    if normalized.endswith("?"):
        return "query"
    first_word = normalized.split()[0] if normalized.split() else ""
    if first_word in _QUERY_STARTERS:
        return "query"
    if any(normalized.startswith(p) for p in _QUERY_PREFIXES):
        return "query"

    # Ambiguous — let the LLM decide; default to store on failure
    return classify_intent(text, cfg)
