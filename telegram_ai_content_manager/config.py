"""Environment loading and database URL helpers."""

import os
from pathlib import Path

DEFAULT_SQLITE_URL = "sqlite:///telegram_ai_content_manager.db"


def load_env(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file without overriding real env vars."""
    env_file = Path(path)
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def database_url() -> str:
    """Return the SQLAlchemy database URL, normalized for psycopg 3."""
    url = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url
