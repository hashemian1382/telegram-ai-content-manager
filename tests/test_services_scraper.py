"""Unit tests for Telegram channel normalization, web scraping, and database persistence."""

import pytest

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.models import SourceChannel, db
from telegram_ai_content_manager.services.scraper import (
    normalize_channel,
    parse_datetime,
    run_scrape,
    scrape_channel,
    source_candidates,
)


@pytest.fixture
def app_context():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_normalize_channel():
    """Test channel name normalization rules."""
    assert normalize_channel("test_channel") == "test_channel"
    assert normalize_channel("@test_channel") == "test_channel"
    assert normalize_channel("https://t.me/test_channel") == "test_channel"
    assert normalize_channel("http://www.t.me/test_channel/123?single=1") == "test_channel"

    with pytest.raises(ValueError, match="valid public Telegram username"):
        normalize_channel("ab")  # too short
    with pytest.raises(ValueError, match="valid public Telegram username"):
        normalize_channel("invalid-char-!")


def test_parse_datetime():
    """Test ISO string datetime parser."""
    dt = parse_datetime("2026-08-11T12:00:00+00:00")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 8
    assert parse_datetime("invalid-date") is None
    assert parse_datetime("") is None


def test_scrape_channel(monkeypatch):
    """Test scraping a Telegram channel preview HTML page."""
    sample_html = """
    <div class="tgme_widget_message">
        <a class="tgme_widget_message_date" href="https://t.me/sample_channel/10"></a>
        <div class="tgme_widget_message_text">متن پست اول</div>
        <time datetime="2026-08-11T10:00:00+00:00"></time>
        <div class="tgme_widget_message_photo"></div>
    </div>
    <div class="tgme_widget_message">
        <a class="tgme_widget_message_date" href="https://t.me/sample_channel/11"></a>
        <div class="tgme_widget_message_text">متن پست دوم</div>
        <time datetime="2026-08-11T11:00:00+00:00"></time>
    </div>
    """

    class MockResponse:
        is_success = True
        status_code = 200
        text = sample_html

        def raise_for_status(self):
            pass

    monkeypatch.setattr("telegram_ai_content_manager.services.scraper.httpx.get", lambda *args, **kwargs: MockResponse())

    posts = scrape_channel("sample_channel")
    assert len(posts) == 2
    assert posts[0]["telegram_post_id"] == 10
    assert posts[0]["text"] == "متن پست اول"
    assert posts[0]["has_media"] is True
    assert posts[1]["telegram_post_id"] == 11
    assert posts[1]["has_media"] is False


def test_run_scrape_and_source_candidates(app_context, monkeypatch):
    """Test running scraper across enabled channels and filtering source candidates."""
    channel = SourceChannel(username="sample_channel", enabled=True)
    db.session.add(channel)
    db.session.commit()

    sample_html = """
    <div class="tgme_widget_message">
        <a class="tgme_widget_message_date" href="https://t.me/sample_channel/5"></a>
        <div class="tgme_widget_message_text">پست نمونه با متن</div>
    </div>
    <div class="tgme_widget_message">
        <a class="tgme_widget_message_date" href="https://t.me/sample_channel/6"></a>
        <div class="tgme_widget_message_text"></div>
    </div>
    """

    class MockResponse:
        is_success = True
        status_code = 200
        text = sample_html

        def raise_for_status(self):
            pass

    monkeypatch.setattr("telegram_ai_content_manager.services.scraper.httpx.get", lambda *args, **kwargs: MockResponse())

    res = run_scrape()
    assert res["channels"] == 1
    assert res["found"] == 2
    assert res["new"] == 2
    assert res["errors"] == []

    # Check source_candidates only returns posts with text > 0
    candidates = source_candidates()
    assert len(candidates) == 1
    assert candidates[0].telegram_post_id == 5
