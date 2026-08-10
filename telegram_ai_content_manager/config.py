"""Configuration loading and database URL normalization."""

import os
from pathlib import Path


def load_env(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs without overwriting the process environment."""
    env_file = Path(path)
    if not env_file.is_file():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def database_url(value: str | None = None) -> str:
    """Return a SQLAlchemy URL compatible with psycopg 3 on hosted Postgres."""
    url = value or os.getenv("DATABASE_URL", "sqlite:///telegram_ai_content_manager.db")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCRAPER_LIMIT = int(os.getenv("SCRAPER_LIMIT", "10"))
    SCRAPER_TIMEOUT = float(os.getenv("SCRAPER_TIMEOUT", "20"))
