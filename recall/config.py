import os
from dataclasses import dataclass

from dotenv import load_dotenv

_REQUIRED = ["SUPABASE_URL", "GEMINI_API_KEY", "CHAT_MODEL", "EMBED_MODEL"]


class ConfigError(Exception):
    pass


@dataclass
class Config:
    supabase_url: str
    supabase_key: str
    gemini_api_key: str
    chat_model: str
    embed_model: str
    embed_dim: int = 768
    top_k: int = 5
    user_id: str = "00000000-0000-0000-0000-000000000001"
    supabase_service_key: str | None = None


def load_config() -> Config:
    load_dotenv()
    missing = [v for v in _REQUIRED if not os.getenv(v)]
    # Phase 5+: prefer SUPABASE_ANON_KEY; fall back to SUPABASE_KEY for legacy .env files
    if not os.getenv("SUPABASE_ANON_KEY") and not os.getenv("SUPABASE_KEY"):
        missing.append("SUPABASE_ANON_KEY (or SUPABASE_KEY)")
    if missing:
        lines = "\n".join(f"  {v}" for v in missing)
        raise ConfigError(
            f"Missing required environment variables:\n{lines}\n\n"
            "Copy .env.example to .env and fill in the values.\n"
            "See README.md for setup instructions."
        )
    return Config(
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_key=os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", ""),
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        chat_model=os.environ["CHAT_MODEL"],
        embed_model=os.environ["EMBED_MODEL"],
        embed_dim=int(os.getenv("EMBED_DIM", "768")),
        top_k=int(os.getenv("TOP_K", "5")),
        user_id=os.getenv("RECALL_USER_ID", "00000000-0000-0000-0000-000000000001"),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY"),
    )
