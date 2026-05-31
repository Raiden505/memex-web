from collections.abc import Generator

from google import genai
from google.genai import types

from recall.config import Config
from recall.models import Intent, SearchResult

_NO_MEMORIES = "I don't have anything saved about that yet."

_SYSTEM_PROMPT = (
    "You are a personal memory assistant. "
    "Answer the user's question using ONLY the memories listed below. "
    "Be concise and natural. "
    "If the memories don't contain the answer, say you don't have anything saved about that. "
    "Never invent details."
)


def synthesize_answer(question: str, memories: list[SearchResult], cfg: Config) -> str:
    if not memories:
        return _NO_MEMORIES

    memory_lines = "\n".join(
        f"{i + 1}. [{r.created_at[:10]}] {r.content}"
        for i, r in enumerate(memories)
    )
    user_message = f"Memories:\n{memory_lines}\n\nQuestion: {question}"

    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
        ),
    )
    return response.text.strip()


def synthesize_answer_stream(question: str, memories: list[SearchResult], cfg: Config) -> Generator[str, None, None]:
    if not memories:
        yield _NO_MEMORIES
        return

    memory_lines = "\n".join(
        f"{i + 1}. [{r.created_at[:10]}] {r.content}"
        for i, r in enumerate(memories)
    )
    user_message = f"Memories:\n{memory_lines}\n\nQuestion: {question}"

    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content_stream(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
        ),
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


_INTENT_SYSTEM = (
    "You decide whether a message is STORE or QUERY.\n"
    "STORE = the user is telling you something to remember (a fact, idea, task, note).\n"
    "QUERY = the user is asking a question or trying to recall something earlier.\n"
    "Examples:\n"
    '  "remind me to call mom tomorrow"    -> STORE\n'
    '  "I had an idea for a running app"   -> STORE\n'
    '  "my friend mentioned cheap jackets" -> STORE\n'
    '  "what\'s my wifi password?"          -> QUERY\n'
    '  "remind me where I parked"          -> QUERY\n'
    '  "did I have any app ideas?"         -> QUERY\n'
    "Reply with exactly one word: STORE or QUERY."
)


def classify_intent(text: str, cfg: Config) -> Intent:
    try:
        client = genai.Client(api_key=cfg.gemini_api_key)
        response = client.models.generate_content(
            model=cfg.chat_model,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=_INTENT_SYSTEM,
                temperature=0,
            ),
        )
        return "query" if "QUERY" in response.text.strip().upper() else "store"
    except Exception:
        return "store"  # safer to over-save than lose input on failure
