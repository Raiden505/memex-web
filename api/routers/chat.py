import asyncio
import json
import re as _re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import Client

from api.dependencies import get_current_user, get_db
from recall import embeddings, llm, router, store, temporal
from recall.config import load_config

chat_router = APIRouter()
_cfg = load_config()

_FORGET_ALL_RE = _re.compile(
    r"\bforget\s+(everything|all(\s+my)?\s+memories?|it\s+all)\b", _re.IGNORECASE
)
_FORGET_VERB_RE = _re.compile(
    r"^(forget|delete|remove)\s+"
    r"(what\s+i\s+(said|saved|told\s+(you\s+)?)(\s*about\s+)?"
    r"|the\s+memory\s+(of\s+|about\s+)?)?",
    _re.IGNORECASE,
)
# A delete only fans out to many memories when the user explicitly asks for it.
# Without one of these words we delete a single best-matching memory (Phase 25).
_FORGET_BULK_RE = _re.compile(r"\b(everything|all|every|each)\b", _re.IGNORECASE)
_FORGET_FLOOR = 0.6


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


class ChatRequest(BaseModel):
    message: str
    tz: str | None = None
    confirm_forget: list[str] | None = None
    # "recall" forces a grounded semantic lookup of a specific memory, skipping
    # intent routing and temporal/due parsing (Phase 23 memory deep-dive).
    mode: str | None = None


class ChatResponse(BaseModel):
    intent: str
    reply: str
    id: str | None = None
    source: str | None = None
    forget_candidates: list[dict] | None = None


def _handle_query(message: str, user_id: str, db: Client, tz: str | None, semantic_only: bool = False) -> str:
    tz_str = tz or "UTC"
    if not semantic_only:
        # Due-date questions ("what's due today") filter on due_at, not created_at.
        due_rng = temporal.extract_due_range(message, tz=tz_str)
        if due_rng:
            start, end, label = due_rng
            mems = store.list_due_in_range(db, user_id, start, end)
            return llm.summarize_due_window(mems, label, _cfg)
        rng = temporal.extract_range(message, tz=tz_str)
        if rng:
            start, end, label = rng
            mems = store.list_memories_in_range(db, user_id, start, end)
            return llm.summarize_window(mems, label, _cfg)
    query_embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_QUERY")
    results = store.search_memories(db, query_embedding, user_id, _cfg.top_k)
    return llm.synthesize_answer(message, results, _cfg)


def _resolve_forget_candidates(message: str, user_id: str, db: Client, tz: str | None) -> list[dict]:
    tz_str = tz or "UTC"

    if _FORGET_ALL_RE.search(message):
        mems = store.list_memories(db, user_id)
        return [{"id": m.id, "content": m.content, "created_at": m.created_at} for m in mems]

    # Only fan out to a whole date range when the user explicitly asks to delete
    # "everything/all" from it — otherwise a stray date word in a single-memory
    # delete ("forget the dentist appointment on Monday") shouldn't nuke the day.
    if _FORGET_BULK_RE.search(message):
        rng = temporal.extract_range(message, tz=tz_str)
        if rng:
            start, end, _ = rng
            mems = store.list_memories_in_range(db, user_id, start, end)
            return [{"id": m.id, "content": m.content, "created_at": m.created_at} for m in mems]

    # Default: the single best-matching memory.
    target = _FORGET_VERB_RE.sub("", message).strip() or message
    query_embedding = embeddings.embed(target, _cfg, task_type="RETRIEVAL_QUERY")
    results = store.search_memories(db, query_embedding, user_id, _cfg.top_k)
    if results and results[0].similarity >= _FORGET_FLOOR:
        r = results[0]
        return [{"id": r.id, "content": r.content, "created_at": r.created_at}]
    return []


def _apply_tags_bg(mem_id: str, content: str, user_id: str, db: Client) -> None:
    try:
        tags = llm.tag_memory(content, _cfg)
        if tags:
            store.update_metadata(db, mem_id, user_id, {"tags": tags})
    except Exception:
        pass


def _forget_reply(n: int, is_all: bool) -> str:
    if n == 0:
        return "I don't have anything saved about that."
    if is_all:
        return f"I found {n} saved {'memory' if n == 1 else 'memories'}. This will delete all of them — are you sure?"
    if n == 1:
        return "I found 1 memory about that — delete it?"
    return f"I found {n} memories about that — delete them?"


@chat_router.post("")
async def chat(
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    stream: bool = Query(False),
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    # Step 2 of forget: user confirmed — skip routing and delete immediately
    if body.confirm_forget is not None:
        try:
            deleted = store.delete_memories(db, body.confirm_forget, user_id)
            reply = f"Forgotten — removed {deleted}." if deleted else "Nothing to remove."
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Delete failed: {exc}")

        if stream:
            async def _confirm_stream():
                yield _sse({"t": reply})
                yield _sse({"done": True})
            return StreamingResponse(
                _confirm_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        return ChatResponse(intent="forget", reply=reply, source="none")

    # Memory deep-dive: skip routing, go straight to a grounded semantic lookup.
    semantic_only = body.mode == "recall"
    if semantic_only:
        intent = "query"
    else:
        try:
            intent = router.route(body.message, _cfg)
        except Exception:
            intent = "store"

    if stream:
        return StreamingResponse(
            _stream_chat(body.message, intent, user_id, db, body.tz, background_tasks, semantic_only),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    try:
        if intent == "store":
            embedding = embeddings.embed(body.message, _cfg, task_type="RETRIEVAL_DOCUMENT")
            due = temporal.extract_due(body.message, tz=body.tz or "UTC")
            initial_meta = {"due": due.isoformat()} if due else None
            row = store.add_memory(db, body.message, embedding, user_id, metadata=initial_meta)
            background_tasks.add_task(_apply_tags_bg, row["id"], body.message, user_id, db)
            return ChatResponse(intent="store", reply=llm.save_ack(), id=row["id"], source="memory")

        if intent == "general":
            reply = llm.chat_general(body.message, _cfg)
            return ChatResponse(intent="general", reply=reply, id=None, source="general")

        if intent == "forget":
            candidates = _resolve_forget_candidates(body.message, user_id, db, body.tz)
            n = len(candidates)
            is_all = bool(_FORGET_ALL_RE.search(body.message))
            reply = _forget_reply(n, is_all)
            return ChatResponse(
                intent="forget",
                reply=reply,
                source="none",
                forget_candidates=candidates if candidates else None,
            )

        # query
        answer = _handle_query(body.message, user_id, db, body.tz, semantic_only)
        empty = answer == llm._NO_MEMORIES or answer.startswith(("Nothing saved", "Nothing due"))
        source = "none" if empty else "memory"
        return ChatResponse(intent="query", reply=answer, source=source)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")


async def _stream_chat(
    message: str, intent: str, user_id: str, db: Client, tz: str | None, bg: BackgroundTasks,
    semantic_only: bool = False,
):
    try:
        if intent == "store":
            embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_DOCUMENT")
            due = temporal.extract_due(message, tz=tz or "UTC")
            initial_meta = {"due": due.isoformat()} if due else None
            row = store.add_memory(db, message, embedding, user_id, metadata=initial_meta)
            bg.add_task(_apply_tags_bg, row["id"], message, user_id, db)
            yield _sse({"t": llm.save_ack()})
            yield _sse({"done": True})

        elif intent == "general":
            async for token in llm.chat_general_stream_async(message, _cfg):
                yield _sse({"t": token})
                await asyncio.sleep(0)
            yield _sse({"done": True})

        elif intent == "forget":
            candidates = _resolve_forget_candidates(message, user_id, db, tz)
            n = len(candidates)
            is_all = bool(_FORGET_ALL_RE.search(message))
            reply = _forget_reply(n, is_all)
            yield _sse({"t": reply})
            if candidates:
                yield _sse({"fc": candidates})
            yield _sse({"done": True})

        else:
            tz_str = tz or "UTC"
            due_rng = None if semantic_only else temporal.extract_due_range(message, tz=tz_str)
            rng = None if semantic_only else temporal.extract_range(message, tz=tz_str)
            if due_rng:
                start, end, label = due_rng
                mems = store.list_due_in_range(db, user_id, start, end)
                async for token in llm.summarize_due_window_stream_async(mems, label, _cfg):
                    yield _sse({"t": token})
                    await asyncio.sleep(0)
            elif rng:
                start, end, label = rng
                mems = store.list_memories_in_range(db, user_id, start, end)
                async for token in llm.summarize_window_stream_async(mems, label, _cfg):
                    yield _sse({"t": token})
                    await asyncio.sleep(0)
            else:
                query_embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_QUERY")
                results = store.search_memories(db, query_embedding, user_id, _cfg.top_k)
                async for token in llm.synthesize_answer_stream_async(message, results, _cfg):
                    yield _sse({"t": token})
                    await asyncio.sleep(0)
            yield _sse({"done": True})

    except Exception as exc:
        yield _sse({"error": str(exc)})
        yield _sse({"done": True})
