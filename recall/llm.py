import random
from collections.abc import Generator

from google import genai
from google.genai import types

from recall.config import Config
from recall.models import Intent, Memory, SearchResult
from recall.prompts import (
    SAVE_ACKS,
    _DUE_SUMMARY_SYSTEM,
    _INTENT_SYSTEM,
    _NO_MEMORIES,
    _PERSONA_PROMPT,
    _SUMMARY_SYSTEM,
    _SYSTEM_PROMPT,
    _TAG_SYSTEM,
)

_VALID_TAGS = frozenset({"idea", "task", "person", "place", "work", "personal", "date", "misc"})

# Phase 23: drop weakly-matching memories before synthesis so irrelevant notes
# don't pollute the answer. `search_memories` returns results sorted by descending
# similarity, so the first item is the strongest match.
_RELEVANCE_FLOOR = 0.2
_RELEVANCE_SPREAD = 0.2


def _filter_relevant(memories: list[SearchResult]) -> list[SearchResult]:
    if not memories:
        return []
    top = memories[0].similarity
    cutoff = max(_RELEVANCE_FLOOR, top - _RELEVANCE_SPREAD)
    return [m for m in memories if m.similarity >= cutoff]


def save_ack(content: str | None = None, rng=None) -> str:
    chooser = rng if rng is not None else random
    return chooser.choice(SAVE_ACKS)


def tag_memory(content: str, cfg: Config) -> list[str]:
    try:
        client = genai.Client(api_key=cfg.gemini_api_key)
        response = client.models.generate_content(
            model=cfg.chat_model,
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=_TAG_SYSTEM,
                temperature=0,
            ),
        )
        raw = response.text.strip().lower()
        parts = [p.strip() for p in raw.split(",")]
        return [p for p in parts if p in _VALID_TAGS]
    except Exception:
        return []


def synthesize_answer(question: str, memories: list[SearchResult], cfg: Config) -> str:
    memories = _filter_relevant(memories)
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
    memories = _filter_relevant(memories)
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


async def synthesize_answer_stream_async(question: str, memories: list[SearchResult], cfg: Config):
    memories = _filter_relevant(memories)
    if not memories:
        yield _NO_MEMORIES
        return

    memory_lines = "\n".join(
        f"{i + 1}. [{r.created_at[:10]}] {r.content}"
        for i, r in enumerate(memories)
    )
    user_message = f"Memories:\n{memory_lines}\n\nQuestion: {question}"

    client = genai.Client(api_key=cfg.gemini_api_key)
    async for chunk in await client.aio.models.generate_content_stream(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
        ),
    ):
        if chunk.text:
            yield chunk.text


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
        if "FORGET" in reply:
            return "forget"
        return "store"
    except Exception:
        return "store"  # safer to over-save than lose input on failure


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


async def chat_general_stream_async(message: str, cfg: Config):
    client = genai.Client(api_key=cfg.gemini_api_key)
    async for chunk in await client.aio.models.generate_content_stream(
        model=cfg.chat_model,
        contents=message,
        config=types.GenerateContentConfig(
            system_instruction=_PERSONA_PROMPT,
            temperature=0.4,
        ),
    ):
        if chunk.text:
            yield chunk.text


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


async def summarize_window_stream_async(memories: list[Memory], label: str, cfg: Config):
    if not memories:
        yield f"Nothing saved {label}."
        return

    memory_lines = "\n".join(
        f"{i + 1}. [{m.created_at[:19]}] {m.content}"
        for i, m in enumerate(memories)
    )
    user_message = f"Time window: {label}\n\nItems:\n{memory_lines}"

    client = genai.Client(api_key=cfg.gemini_api_key)
    async for chunk in await client.aio.models.generate_content_stream(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_SUMMARY_SYSTEM,
            temperature=0.2,
        ),
    ):
        if chunk.text:
            yield chunk.text


def _due_lines(memories: list[Memory]) -> str:
    return "\n".join(
        f"{i + 1}. (due {((m.metadata or {}).get('due') or '')[:16]}) {m.content}"
        for i, m in enumerate(memories)
    )


def summarize_due_window(memories: list[Memory], label: str, cfg: Config) -> str:
    if not memories:
        return f"Nothing due {label}."

    user_message = f"These items are due {label}:\n{_due_lines(memories)}"
    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_DUE_SUMMARY_SYSTEM,
            temperature=0.2,
        ),
    )
    return response.text.strip()


async def summarize_due_window_stream_async(memories: list[Memory], label: str, cfg: Config):
    if not memories:
        yield f"Nothing due {label}."
        return

    user_message = f"These items are due {label}:\n{_due_lines(memories)}"
    client = genai.Client(api_key=cfg.gemini_api_key)
    async for chunk in await client.aio.models.generate_content_stream(
        model=cfg.chat_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_DUE_SUMMARY_SYSTEM,
            temperature=0.2,
        ),
    ):
        if chunk.text:
            yield chunk.text
