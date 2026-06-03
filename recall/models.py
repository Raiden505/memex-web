from dataclasses import dataclass
from typing import Literal


@dataclass
class Memory:
    id: str
    content: str
    created_at: str
    user_id: str


@dataclass
class SearchResult:
    id: str
    content: str
    created_at: str
    similarity: float  # 0..1, higher = more similar


Intent = Literal["store", "query", "general", "forget"]
