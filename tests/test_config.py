"""Unit tests for configuration, environment loading, and model list parsing."""

import os

from telegram_ai_content_manager.config import (
    _strip_inline_comment,
    database_url,
    get_configured_models,
    load_env,
)


def test_strip_inline_comment():
    """Test removing comments outside quoted strings."""
    assert _strip_inline_comment("KEY=value # comment") == "KEY=value"
    assert _strip_inline_comment('KEY="value # not a comment" # real comment') == 'KEY="value # not a comment"'
    assert _strip_inline_comment("KEY='value'") == "KEY='value'"
    assert _strip_inline_comment("no_comment_here") == "no_comment_here"


def test_load_env_file_parsing(tmp_path, monkeypatch):
    """Test loading a .env file with various formatting edge cases."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Header comment\n"
        "TEST_KEY1=val1 # inline comment\n"
        'TEST_KEY2="val2 with space" # comment\n'
        "TEST_KEY3='val3'\n"
        "   \n"
        "INVALID_LINE_NO_EQUAL\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TEST_KEY1", raising=False)
    monkeypatch.delenv("TEST_KEY2", raising=False)
    monkeypatch.delenv("TEST_KEY3", raising=False)

    load_env(str(env_file))

    assert os.getenv("TEST_KEY1") == "val1"
    assert os.getenv("TEST_KEY2") == "val2 with space"
    assert os.getenv("TEST_KEY3") == "val3"


def test_database_url_normalization(monkeypatch):
    """Test PostgreSQL schema normalization for Psycopg 3 compatibility."""
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
    assert database_url() == "postgresql+psycopg://user:pass@host:5432/db"

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
    assert database_url() == "postgresql+psycopg://user:pass@host:5432/db"

    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    assert database_url() == "sqlite:///test.db"


def test_get_configured_models(monkeypatch):
    """Test parsing and display names of configured AI models."""
    monkeypatch.setenv(
        "GEMINI_MODELS",
        "gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b,gemma-4-26b",
    )
    models = get_configured_models()
    assert len(models) == 7
    ids = [m["id"] for m in models]
    assert "gemini-3.6-flash" in ids
    assert "gemma-4-31b" in ids
    assert models[0]["name"] == "Gemini 3.6 Flash"
    assert models[-1]["name"] == "Gemma 4 26B"
