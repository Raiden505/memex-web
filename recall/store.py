from supabase import Client, create_client

from recall.config import Config
from recall.models import Memory, SearchResult


def get_client(cfg: Config) -> Client:
    return create_client(cfg.supabase_url, cfg.supabase_key)


def add_memory(client: Client, content: str, embedding: list[float] | None, user_id: str) -> dict:
    row: dict = {"content": content, "user_id": user_id}
    if embedding is not None:
        row["embedding"] = embedding
    result = client.table("memories").insert(row).execute()
    return result.data[0]


def list_memories(client: Client, user_id: str) -> list[Memory]:
    result = (
        client.table("memories")
        .select("id, content, created_at, user_id")
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
        )
        for row in result.data
    ]
