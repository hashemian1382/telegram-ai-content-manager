import os
from pathlib import Path


def load_env(path: str = ".env") -> None:
    env_file = Path(path)
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///channel_hub.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODELS = tuple(item.strip() for item in os.getenv("GEMINI_MODELS", "gemini-3.5-flash").split(",") if item.strip())
    SCRAPER_LIMIT = int(os.getenv("SCRAPER_LIMIT", "10"))
    SCRAPER_TIMEOUT = float(os.getenv("SCRAPER_TIMEOUT", "20"))
