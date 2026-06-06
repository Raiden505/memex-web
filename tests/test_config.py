"""Tests for recall/config.py — validates env var handling and ConfigError.

load_config() calls load_dotenv() which reads from the project's .env file.
We patch load_dotenv to be a no-op so that tests are isolated from real credentials.
"""

import os
import pytest
from unittest.mock import patch


_NOOP_DOTENV = patch("recall.config.load_dotenv")

_BASE_VARS = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "anon-key-test",
    "GEMINI_API_KEY": "gemini-test-key",
    "CHAT_MODEL": "gemini-2.5-flash",
    "EMBED_MODEL": "gemini-embedding-001",
}


def _set_base(monkeypatch):
    for k, v in _BASE_VARS.items():
        monkeypatch.setenv(k, v)


def test_load_config_raises_on_missing_vars(monkeypatch):
    for var in ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_KEY",
                "GEMINI_API_KEY", "CHAT_MODEL", "EMBED_MODEL"]:
        monkeypatch.delenv(var, raising=False)

    from recall.config import load_config, ConfigError
    with _NOOP_DOTENV:
        with pytest.raises(ConfigError) as exc_info:
            load_config()
    error_msg = str(exc_info.value)
    assert "Missing required environment variables" in error_msg
    assert "SUPABASE_URL" in error_msg


def test_load_config_succeeds_with_all_vars(monkeypatch):
    _set_base(monkeypatch)
    from recall.config import load_config
    with _NOOP_DOTENV:
        cfg = load_config()
    assert cfg.supabase_url == "https://test.supabase.co"
    assert cfg.supabase_key == "anon-key-test"
    assert cfg.gemini_api_key == "gemini-test-key"
    assert cfg.chat_model == "gemini-2.5-flash"
    assert cfg.embed_model == "gemini-embedding-001"


def test_supabase_key_fallback_to_supabase_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_KEY", "legacy-service-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("CHAT_MODEL", "test")
    monkeypatch.setenv("EMBED_MODEL", "test")

    from recall.config import load_config
    with _NOOP_DOTENV:
        cfg = load_config()
    assert cfg.supabase_key == "legacy-service-key"


def test_default_embed_dim_is_768(monkeypatch):
    _set_base(monkeypatch)
    monkeypatch.delenv("EMBED_DIM", raising=False)
    from recall.config import load_config
    with _NOOP_DOTENV:
        cfg = load_config()
    assert cfg.embed_dim == 768


def test_default_top_k_is_5(monkeypatch):
    _set_base(monkeypatch)
    monkeypatch.delenv("TOP_K", raising=False)
    from recall.config import load_config
    with _NOOP_DOTENV:
        cfg = load_config()
    assert cfg.top_k == 5


def test_custom_top_k(monkeypatch):
    _set_base(monkeypatch)
    monkeypatch.setenv("TOP_K", "10")
    from recall.config import load_config
    with _NOOP_DOTENV:
        cfg = load_config()
    assert cfg.top_k == 10


def test_missing_only_supabase_url(monkeypatch):
    for var in ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_KEY",
                "GEMINI_API_KEY", "CHAT_MODEL", "EMBED_MODEL"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "key")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("CHAT_MODEL", "m")
    monkeypatch.setenv("EMBED_MODEL", "m")

    from recall.config import load_config, ConfigError
    with _NOOP_DOTENV:
        with pytest.raises(ConfigError) as exc:
            load_config()
    assert "SUPABASE_URL" in str(exc.value)


def test_config_error_message_helpful(monkeypatch):
    for var in ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_KEY",
                "GEMINI_API_KEY", "CHAT_MODEL", "EMBED_MODEL"]:
        monkeypatch.delenv(var, raising=False)

    from recall.config import load_config, ConfigError
    with _NOOP_DOTENV:
        with pytest.raises(ConfigError) as exc:
            load_config()
    msg = str(exc.value)
    assert ".env" in msg or "environment" in msg.lower()
