from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from api.dependencies import get_current_user, get_db
from recall import embeddings, store
from recall.config import load_config

router = APIRouter()
_cfg = load_config()


class StoreRequest(BaseModel):
    content: str


class MemoryOut(BaseModel):
    id: str
    content: str
    created_at: str
    metadata: dict | None = None


class UpdateRequest(BaseModel):
    content: str


class PinRequest(BaseModel):
    pinned: bool


@router.post("", status_code=201)
async def create_memory(
    body: StoreRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    try:
        row = store.add_memory(db, body.content, None, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {exc}")
    return {"id": row["id"], "created_at": row["created_at"]}


@router.get("")
async def list_memories(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> list[MemoryOut]:
    try:
        memories = store.list_memories(db, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list memories: {exc}")
    return [MemoryOut(id=m.id, content=m.content, created_at=m.created_at, metadata=m.metadata) for m in memories]


@router.patch("/{mem_id}")
async def update_memory(
    mem_id: str,
    body: UpdateRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    try:
        embedding = embeddings.embed(body.content, _cfg, task_type="RETRIEVAL_DOCUMENT")
        row = store.update_memory(db, mem_id, user_id, body.content, embedding)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update memory: {exc}")
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {"id": row["id"], "updated": True}


@router.post("/{mem_id}/pin")
async def pin_memory(
    mem_id: str,
    body: PinRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    try:
        row = store.set_pinned(db, mem_id, user_id, body.pinned)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to pin memory: {exc}")
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {"id": row["id"], "pinned": body.pinned}


@router.get("/count")
async def memory_count(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    try:
        total = store.count_memories(db, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to count memories: {exc}")
    return {"total": total}


@router.delete("/{mem_id}")
async def delete_memory(
    mem_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    try:
        deleted = store.delete_memory(db, mem_id, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {exc}")
    if not deleted:
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": True}
