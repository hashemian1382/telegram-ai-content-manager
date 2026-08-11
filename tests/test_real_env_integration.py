"""Real environment integration test using .env and local SQLite database."""

import os
from pathlib import Path

import pytest

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.config import get_configured_models, load_env
from telegram_ai_content_manager.models import SourceChannel, SourcePost, db
from telegram_ai_content_manager.services import create_direct_draft, create_random_draft, run_scrape


def test_real_env_loading_and_config():
    """Test loading the real .env configuration file."""
    env_path = Path(".env")
    if not env_path.exists():
        pytest.skip("No .env file found in workspace.")

    load_env(".env")
    assert os.getenv("SECRET_KEY") is not None
    assert "telegram_ai_content_manager.db" in os.getenv("DATABASE_URL", "")
    assert os.getenv("TELEGRAM_BOT_TOKEN", "").startswith("8140146895:")
    assert os.getenv("TELEGRAM_CHANNEL_ID") == "@AI_Tech_Data"

    models = get_configured_models()
    model_ids = {m["id"] for m in models}
    expected = {
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    }
    assert expected.issubset(model_ids)


def test_real_channel_scraping_and_draft_creation():
    """Test creating app with real .env, scraping @AI_Tech_Data, and drafting."""
    app = create_app()
    with app.app_context():
        # Ensure database tables exist
        db.create_all()

        channel = SourceChannel.query.filter_by(username="AI_Tech_Data").first()
        if not channel:
            channel = SourceChannel(username="AI_Tech_Data")
            db.session.add(channel)
            db.session.commit()

        assert channel.id is not None
        assert channel.username == "AI_Tech_Data"

        # Run real scrape against Telegram channel preview
        stats = run_scrape(limit=5, timeout=20)
        assert stats["channels"] >= 1
        assert stats["found"] > 0

        # Check posts persisted
        posts_count = SourcePost.query.filter_by(channel_id=channel.id).count()
        assert posts_count > 0

        # Create random draft from scraped post
        rand_draft = create_random_draft()
        assert rand_draft.id is not None
        assert len(rand_draft.text) > 0
        assert rand_draft.status == "draft"

        # Create direct draft
        dir_draft = create_direct_draft("تست یکپارچگی محیط لوکال پروژه")
        assert dir_draft.id is not None
        assert dir_draft.text == "تست یکپارچگی محیط لوکال پروژه"
