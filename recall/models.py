from dataclasses import dataclass
from typing import Literal


@dataclass
class Memory:
    id: str
    content: str
    created_at: str
    user_id: str
    metadata: dict | None = None


@dataclass
class SearchResult:
    id: str
    content: str
    created_at: str
    similarity: float  # 0..1, higher = more similar
    metadata: dict | None = None


Intent = Literal["store", "query", "general", "forget"]
