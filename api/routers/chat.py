from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import Client

from api.dependencies import get_current_user, get_db
from recall import embeddings, llm, router, store, temporal
from recall.config import load_config

chat_router = APIRouter()
_cfg = load_config()


class ChatRequest(BaseModel):
    message: str
    tz: str | None = None


class ChatResponse(BaseModel):
    intent: str
    reply: str
    id: str | None = None
    source: str | None = None


def _handle_query(message: str, user_id: str, db: Client, tz: str | None) -> str:
    tz_str = tz or "UTC"
    rng = temporal.extract_range(message, tz=tz_str)
    if rng:
        start, end, label = rng
        mems = store.list_memories_in_range(db, user_id, start, end)
        answer = llm.summarize_window(mems, label, _cfg)
        return answer
    query_embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_QUERY")
    results = store.search_memories(db, query_embedding, user_id, _cfg.top_k)
    return llm.synthesize_answer(message, results, _cfg)


@chat_router.post("")
async def chat(
    body: ChatRequest,
    stream: bool = Query(False),
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    try:
        intent = router.route(body.message, _cfg)
    except Exception:
        intent = "store"

    if stream:
        return StreamingResponse(
            _stream_chat(body.message, intent, user_id, db, body.tz),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    try:
        if intent == "store":
            embedding = embeddings.embed(body.message, _cfg, task_type="RETRIEVAL_DOCUMENT")
            row = store.add_memory(db, body.message, embedding, user_id)
            return ChatResponse(intent="store", reply="Saved.", id=row["id"], source="memory")
        elif intent == "general":
            reply = llm.chat_general(body.message, _cfg)
            return ChatResponse(intent="general", reply=reply, id=None, source="general")
        else:
            answer = _handle_query(body.message, user_id, db, body.tz)
            source = "none" if answer == llm._NO_MEMORIES or answer.startswith("Nothing saved") else "memory"
            return ChatResponse(intent="query", reply=answer, source=source)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")


async def _stream_chat(message: str, intent: str, user_id: str, db: Client, tz: str | None):
    try:
        if intent == "store":
            embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_DOCUMENT")
            row = store.add_memory(db, message, embedding, user_id)
            yield f"data: Saved.\n\n"
            yield f"data: [DONE]\n\n"
        elif intent == "general":
            for token in llm.chat_general_stream(message, _cfg):
                yield f"data: {token}\n\n"
            yield f"data: [DONE]\n\n"
        else:
            tz_str = tz or "UTC"
            rng = temporal.extract_range(message, tz=tz_str)
            if rng:
                start, end, label = rng
                mems = store.list_memories_in_range(db, user_id, start, end)
                for token in llm.summarize_window_stream(mems, label, _cfg):
                    yield f"data: {token}\n\n"
            else:
                query_embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_QUERY")
                results = store.search_memories(db, query_embedding, user_id, _cfg.top_k)
                for token in llm.synthesize_answer_stream(message, results, _cfg):
                    yield f"data: {token}\n\n"
            yield f"data: [DONE]\n\n"
    except Exception as exc:
        yield f"data: Error: {exc}\n\n"
        yield f"data: [DONE]\n\n"
