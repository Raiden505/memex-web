from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from api.dependencies import get_current_user, get_db
from recall import store
from recall.config import load_config

router = APIRouter()
_cfg = load_config()


class StoreRequest(BaseModel):
    content: str


class MemoryOut(BaseModel):
    id: str
    content: str
    created_at: str


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
    return [MemoryOut(id=m.id, content=m.content, created_at=m.created_at) for m in memories]


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
