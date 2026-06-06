from datetime import datetime

from supabase import Client, create_client

from recall.config import Config
from recall.models import Memory, SearchResult


def get_client(cfg: Config) -> Client:
    return create_client(cfg.supabase_url, cfg.supabase_key)


def add_memory(
    client: Client,
    content: str,
    embedding: list[float] | None,
    user_id: str,
    metadata: dict | None = None,
) -> dict:
    row: dict = {"content": content, "user_id": user_id}
    if embedding is not None:
        row["embedding"] = embedding
    if metadata:
        row["metadata"] = metadata
        # Mirror the due date into the typed, indexed column (Phase 24).
        if metadata.get("due"):
            row["due_at"] = metadata["due"]
    result = client.table("memories").insert(row).execute()
    return result.data[0]


def list_memories(client: Client, user_id: str) -> list[Memory]:
    result = (
        client.table("memories")
        .select("id, content, created_at, user_id, metadata")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [Memory(**row) for row in result.data]


def delete_memory(client: Client, mem_id: str, user_id: str) -> bool:
    result = (
        client.table("memories")
        .delete()
        .eq("id", mem_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


def count_memories(client: Client, user_id: str) -> int:
    result = (
        client.table("memories")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return result.count or 0


def search_memories(
    client: Client, query_embedding: list[float], user_id: str, k: int
) -> list[SearchResult]:
    result = client.rpc(
        "match_memories",
        {"query_embedding": query_embedding, "match_user_id": user_id, "match_count": k},
    ).execute()
    return [
        SearchResult(
            id=row["id"],
            content=row["content"],
            created_at=row["created_at"],
            similarity=row["similarity"],
            metadata=row.get("metadata"),
        )
        for row in result.data
    ]


def delete_memories(client: Client, ids: list[str], user_id: str) -> int:
    if not ids:
        return 0
    result = (
        client.table("memories")
        .delete()
        .in_("id", ids)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data)


def update_memory(
    client: Client, mem_id: str, user_id: str, content: str, embedding: list[float]
) -> dict:
    result = (
        client.table("memories")
        .update({"content": content, "embedding": embedding})
        .eq("id", mem_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def set_pinned(
    client: Client, mem_id: str, user_id: str, pinned: bool
) -> dict:
    # Merge so pinning doesn't wipe tags/due already in metadata.
    return update_metadata(client, mem_id, user_id, {"pinned": pinned})


def search_memories_text(
    client: Client, user_id: str, query: str
) -> list[Memory]:
    result = (
        client.table("memories")
        .select("id, content, created_at, user_id, metadata")
        .eq("user_id", user_id)
        .ilike("content", f"%{query}%")
        .order("created_at", desc=True)
        .execute()
    )
    return [Memory(**row) for row in result.data]


def content_exists(client: Client, user_id: str, content: str) -> bool:
    result = (
        client.table("memories")
        .select("id")
        .eq("user_id", user_id)
        .ilike("content", content)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


def update_metadata(client: Client, mem_id: str, user_id: str, updates: dict) -> dict:
    result = (
        client.table("memories")
        .select("metadata")
        .eq("id", mem_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return {}
    current = result.data[0].get("metadata") or {}
    merged = {**current, **updates}
    payload: dict = {"metadata": merged}
    # Keep the typed due_at column in sync whenever the due date changes (Phase 24).
    if "due" in updates:
        payload["due_at"] = updates["due"]
    result = (
        client.table("memories")
        .update(payload)
        .eq("id", mem_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def list_due(client: Client, user_id: str, before: datetime) -> list[Memory]:
    result = (
        client.table("memories")
        .select("id, content, created_at, user_id, metadata")
        .eq("user_id", user_id)
        .filter("due_at", "not.is", "null")
        .filter("due_at", "lte", before.isoformat())
        .order("due_at", desc=False)
        .execute()
    )
    return [Memory(**row) for row in result.data]


def list_due_in_range(
    client: Client, user_id: str, start: datetime, end: datetime
) -> list[Memory]:
    """Memories whose due date falls in [start, end), soonest first (Phase 24)."""
    result = (
        client.table("memories")
        .select("id, content, created_at, user_id, metadata")
        .eq("user_id", user_id)
        .filter("due_at", "not.is", "null")
        .gte("due_at", start.isoformat())
        .lt("due_at", end.isoformat())
        .order("due_at", desc=False)
        .execute()
    )
    return [Memory(**row) for row in result.data]


def list_memories_in_range(
    client: Client, user_id: str, start: datetime, end: datetime
) -> list[Memory]:
    result = (
        client.table("memories")
        .select("id, content, created_at, user_id")
        .eq("user_id", user_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .order("created_at", desc=False)
        .execute()
    )
    return [Memory(**row) for row in result.data]
