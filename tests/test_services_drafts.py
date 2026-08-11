"""Unit tests for draft creation, text validation, and Telegram channel publishing."""

import pytest

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.models import SourceChannel, SourcePost, db
from telegram_ai_content_manager.services.drafts import (
    create_direct_draft,
    create_random_draft,
    publish_draft,
    validate_text,
)


@pytest.fixture
def app_context():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_validate_text():
    """Test message text length validation."""
    assert validate_text("   متن معتبر   ") == "متن معتبر"
    with pytest.raises(ValueError, match="1 to 4096 characters"):
        validate_text("")
    with pytest.raises(ValueError, match="1 to 4096 characters"):
        validate_text("A" * 4097)


def test_create_direct_draft(app_context):
    """Test manual draft creation and persistence."""
    draft = create_direct_draft("تست پیش‌نویس دستی")
    assert draft.id is not None
    assert draft.text == "تست پیش‌نویس دستی"
    assert draft.status == "draft"


def test_create_random_draft(app_context):
    """Test selecting a random text post from DB."""
    # Should raise error when no text posts exist
    with pytest.raises(ValueError, match="No text posts are available"):
        create_random_draft()

    channel = SourceChannel(username="chan")
    db.session.add(channel)
    db.session.commit()

    post = SourcePost(
        channel_id=channel.id,
        telegram_post_id=1,
        url="https://t.me/chan/1",
        text="متن پست برای انتخاب تصادفی",
    )
    db.session.add(post)
    db.session.commit()

    draft = create_random_draft()
    assert draft.id is not None
    assert draft.source_post_id == post.id
    assert draft.text == "متن پست برای انتخاب تصادفی"


def test_publish_draft_success_and_errors(app_context, monkeypatch):
    """Test publishing an approved draft to a Telegram channel."""
    draft = create_direct_draft("پیش‌نویس تستی برای انتشار")

    # Missing credentials should raise ValueError
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="must be configured"):
        publish_draft(draft)

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@fake_channel")

    class MockSuccessResponse:
        def json(self):
            return {"ok": True, "result": {"message_id": 54321}}

    monkeypatch.setattr("telegram_ai_content_manager.services.drafts.httpx.post", lambda *args, **kwargs: MockSuccessResponse())

    pub_draft = publish_draft(draft)
    assert pub_draft.status == "published"
    assert pub_draft.telegram_message_id == 54321
    assert pub_draft.published_at is not None

    # Publishing already published draft should raise ValueError
    with pytest.raises(ValueError, match="already been published"):
        publish_draft(pub_draft)


def test_publish_draft_api_error(app_context, monkeypatch):
    """Test Telegram API returning an error description."""
    draft = create_direct_draft("تست خطای تلگرام")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@fake_channel")

    class MockErrorResponse:
        def json(self):
            return {"ok": False, "description": "Bad Request: chat not found"}

    monkeypatch.setattr("telegram_ai_content_manager.services.drafts.httpx.post", lambda *args, **kwargs: MockErrorResponse())

    with pytest.raises(ValueError, match="Telegram error: Bad Request: chat not found"):
        publish_draft(draft)
    assert draft.status == "draft"
