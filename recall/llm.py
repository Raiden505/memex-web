from collections.abc import Generator

from google import genai
from google.genai import types

from recall.config import Config
from recall.models import Intent, Memory, SearchResult

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
    "You classify a message as STORE, QUERY, or GENERAL.\n"
    "STORE   = the user is telling you something to remember (a fact, idea, task, note).\n"
    "QUERY   = the user is recalling something PERSONAL they told you earlier.\n"
    "GENERAL = a greeting, small talk, a general-knowledge question, or a question about "
    "what you are / can do — NOT something personal they previously told you.\n"
    "Examples:\n"
    '  "remind me to call mom tomorrow"    -> STORE\n'
    '  "my friend mentioned cheap jackets" -> STORE\n'
    '  "where did I park?"                 -> QUERY\n'
    '  "did I have any app ideas?"         -> QUERY\n'
    '  "hi there"                          -> GENERAL\n'
    '  "what\'s the capital of France?"     -> GENERAL\n'
    '  "what can you do?"                  -> GENERAL\n'
    "Reply with exactly one word: STORE, QUERY, or GENERAL."
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
        reply = response.text.strip().upper()
        if "QUERY" in reply:
            return "query"
        if "GENERAL" in reply:
            return "general"
        return "store"
    except Exception:
        return "store"  # safer to over-save than lose input on failure


_PERSONA_PROMPT = (
    "You are Memex, a personal memory assistant. The user has said something that is not a "
    "memory to store and not a question about their saved memories — it's a greeting, small "
    "talk, or a general question. Reply briefly and warmly. For a greeting, invite them to "
    "tell you something to remember. For a general-knowledge question, answer directly and "
    "concisely. Never claim something is from the user's saved memories. Keep it to a sentence "
    "or two."
)


def chat_general(message: str, cfg: Config) -> str:
    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content(
        model=cfg.chat_model,
        contents=message,
        config=types.GenerateContentConfig(
            system_instruction=_PERSONA_PROMPT,
            temperature=0.4,
        ),
    )
    return response.text.strip()


def chat_general_stream(message: str, cfg: Config) -> Generator[str, None, None]:
    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content_stream(
        model=cfg.chat_model,
        contents=message,
        config=types.GenerateContentConfig(
            system_instruction=_PERSONA_PROMPT,
            temperature=0.4,
        ),
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


_SUMMARY_SYSTEM = (
    "List or summarise what the user saved in the given time window. "
    "Use ONLY the items listed below. Be concise. Do not invent items."
)


def summarize_window(memories: list[Memory], label: str, cfg: Config) -> str:
    if not memories:
        return f"Nothing saved {label}."

    memory_lines = "\n".join(
        f"{i + 1}. [{m.created_at[:19]}] {m.content}"
        for i, m in enumerate(memories)
    )
    user_message = f"Time window: {label}\n\nItems:\n{memory_lines}"

    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_SUMMARY_SYSTEM,
            temperature=0.2,
        ),
    )
    return response.text.strip()


def summarize_window_stream(memories: list[Memory], label: str, cfg: Config) -> Generator[str, None, None]:
    if not memories:
        yield f"Nothing saved {label}."
        return

    memory_lines = "\n".join(
        f"{i + 1}. [{m.created_at[:19]}] {m.content}"
        for i, m in enumerate(memories)
    )
    user_message = f"Time window: {label}\n\nItems:\n{memory_lines}"

    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content_stream(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_SUMMARY_SYSTEM,
            temperature=0.2,
        ),
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text
