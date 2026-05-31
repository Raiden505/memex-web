from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import Client

from api.dependencies import get_current_user, get_db
from recall import embeddings, llm, router, store
from recall.config import load_config

chat_router = APIRouter()
_cfg = load_config()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    intent: str
    reply: str
    id: str | None = None


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
            _stream_chat(body.message, intent, user_id, db),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    try:
        if intent == "store":
            embedding = embeddings.embed(body.message, _cfg, task_type="RETRIEVAL_DOCUMENT")
            row = store.add_memory(db, body.message, embedding, user_id)
            return ChatResponse(intent="store", reply="Saved.", id=row["id"])
        else:
            query_embedding = embeddings.embed(body.message, _cfg, task_type="RETRIEVAL_QUERY")
            results = store.search_memories(db, query_embedding, user_id, _cfg.top_k)
            answer = llm.synthesize_answer(body.message, results, _cfg)
            return ChatResponse(intent="query", reply=answer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")


async def _stream_chat(message: str, intent: str, user_id: str, db: Client):
    try:
        if intent == "store":
            embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_DOCUMENT")
            row = store.add_memory(db, message, embedding, user_id)
            yield f"data: Saved.\n\n"
            yield f"data: [DONE]\n\n"
        else:
            query_embedding = embeddings.embed(message, _cfg, task_type="RETRIEVAL_QUERY")
            results = store.search_memories(db, query_embedding, user_id, _cfg.top_k)
            for token in llm.synthesize_answer_stream(message, results, _cfg):
                yield f"data: {token}\n\n"
            yield f"data: [DONE]\n\n"
    except Exception as exc:
        yield f"data: Error: {exc}\n\n"
        yield f"data: [DONE]\n\n"
