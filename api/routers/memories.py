from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from supabase import Client

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from api.dependencies import get_current_user, get_db
from recall import embeddings, llm, store, temporal
from recall.config import load_config
from recall.models import Memory

router = APIRouter()
_cfg = load_config()


def _apply_tags_bg(mem_id: str, content: str, user_id: str, db: Client) -> None:
    try:
        tags = llm.tag_memory(content, _cfg)
        if tags:
            store.update_metadata(db, mem_id, user_id, {"tags": tags})
    except Exception:
        pass


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


class ImportItem(BaseModel):
    content: str
    created_at: str | None = None


class ImportRequest(BaseModel):
    items: list[ImportItem]


@router.post("", status_code=201)
async def create_memory(
    body: StoreRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    try:
        embedding = embeddings.embed(body.content, _cfg, task_type="RETRIEVAL_DOCUMENT")
        due = temporal.extract_due(body.content)
        initial_meta = {"due": due.isoformat()} if due else None
        row = store.add_memory(db, body.content, embedding, user_id, metadata=initial_meta)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {exc}")
    background_tasks.add_task(_apply_tags_bg, row["id"], body.content, user_id, db)
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


@router.get("/export")
async def export_memories(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> list[dict]:
    try:
        memories = store.list_memories(db, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")
    return [
        {"content": m.content, "created_at": m.created_at, "metadata": m.metadata}
        for m in memories
    ]


@router.post("/import")
async def import_memories(
    body: ImportRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    imported = 0
    skipped = 0
    for item in body.items:
        try:
            if store.content_exists(db, user_id, item.content):
                skipped += 1
                continue
            embedding = embeddings.embed(item.content, _cfg, task_type="RETRIEVAL_DOCUMENT")
            results = store.search_memories(db, embedding, user_id, k=1)
            if results and results[0].similarity >= 0.97:
                skipped += 1
                continue
            store.add_memory(db, item.content, embedding, user_id)
            imported += 1
        except Exception:
            skipped += 1
    return {"imported": imported, "skipped": skipped}


@router.get("/stats")
async def memory_stats(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    try:
        all_mems = store.list_memories(db, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stats failed: {exc}")
    total = len(all_mems)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    added_last_30d = sum(1 for m in all_mems if m.created_at >= cutoff)
    tag_counts: dict[str, int] = {}
    for m in all_mems:
        for tag in (m.metadata or {}).get("tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "total": total,
        "added_last_30d": added_last_30d,
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
    }


@router.get("/due")
async def due_memories(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> list[MemoryOut]:
    before = datetime.now(timezone.utc) + timedelta(days=7)
    try:
        memories = store.list_due(db, user_id, before)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list due memories: {exc}")
    return [MemoryOut(id=m.id, content=m.content, created_at=m.created_at, metadata=m.metadata) for m in memories]


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
