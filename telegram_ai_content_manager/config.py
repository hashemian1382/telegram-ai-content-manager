"""Environment loading and database URL helpers."""

import os
from pathlib import Path

DEFAULT_SQLITE_URL = "sqlite:///telegram_ai_content_manager.db"

# Default models required by project specification
DEFAULT_GEMINI_MODELS = (
    "gemini-3.6-flash,"
    "gemini-3.5-flash,"
    "gemini-3-flash,"
    "gemini-3.5-flash-lite,"
    "gemini-3.1-flash-lite,"
    "gemma-4-31b,"
    "gemma-4-26b"
)

# Friendly display names for UI and API responses
MODEL_DISPLAY_NAMES = {
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini-3-flash": "Gemini 3 Flash",
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite",
    "gemma-4-31b": "Gemma 4 31B",
    "gemma-4-26b": "Gemma 4 26B",
}


def _strip_inline_comment(line: str) -> str:
    """Remove trailing # comments unless inside quotes."""
    in_single = False
    in_double = False
    for idx, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:idx].strip()
    return line.strip()


def load_env(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file without overriding real env vars.
    
    Supports inline comments, single/double quotes, and trailing whitespace.
    """
    env_file = Path(path)
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        line = _strip_inline_comment(line)
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def database_url() -> str:
    """Return the SQLAlchemy database URL, normalized for psycopg 3."""
    url = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL).strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def get_configured_models() -> list[dict[str, str]]:
    """Return the list of enabled AI models with display names."""
    raw = os.getenv("GEMINI_MODELS", DEFAULT_GEMINI_MODELS)
    models = []
    seen = set()
    for item in raw.split(","):
        model_id = item.strip().lower()
        if model_id and model_id not in seen:
            seen.add(model_id)
            display_name = MODEL_DISPLAY_NAMES.get(model_id, model_id.title())
            models.append({"id": model_id, "name": display_name})
    return models
