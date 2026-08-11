"""Comprehensive integration tests for each JSON REST API route and error handler."""

import pytest

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.models import db


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test"})
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app.test_client()


def test_health_endpoint(client):
    """Test GET /health returns status ok."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json["status"] == "ok"


def test_dashboard_endpoint_empty(client):
    """Test GET /api/dashboard initial counters."""
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.json
    assert data["channels"] == 0
    assert data["posts"] == 0
    assert data["drafts"] == 0
    assert data["published"] == 0
    assert data["recent_drafts"] == []


def test_models_endpoint_all_models(client, monkeypatch):
    """Test GET /api/models returns all 7 required models."""
    monkeypatch.setenv(
        "GEMINI_MODELS",
        "gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b,gemma-4-26b",
    )
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.json
    assert len(data["models"]) == 7
    assert data["default_model"] == "gemini-3.6-flash"


def test_get_channels_empty(client):
    """Test listing channels when database is empty."""
    res = client.get("/api/channels")
    assert res.status_code == 200
    assert res.json == []


def test_post_channels_valid(client):
    """Test adding a valid Telegram channel."""
    res = client.post("/api/channels", json={"username": "https://t.me/sample_chan"})
    assert res.status_code == 201
    assert res.json["username"] == "sample_chan"
    assert res.json["enabled"] is True


def test_post_channels_duplicate(client):
    """Test adding an already existing channel returns 409 Conflict."""
    client.post("/api/channels", json={"username": "sample_chan"})
    res_dup = client.post("/api/channels", json={"username": "@sample_chan"})
    assert res_dup.status_code == 409
    assert "already exists" in res_dup.json["error"]


def test_post_channels_invalid_username(client):
    """Test adding an invalid channel username returns 400."""
    res = client.post("/api/channels", json={"username": "a"})
    assert res.status_code == 400
    assert "valid public Telegram username" in res.json["error"]


def test_delete_channel_success(client):
    """Test deleting an existing channel returns 204."""
    post_res = client.post("/api/channels", json={"username": "to_delete_chan"})
    channel_id = post_res.json["id"]
    del_res = client.delete(f"/api/channels/{channel_id}")
    assert del_res.status_code == 204
    assert len(client.get("/api/channels").json) == 0


def test_delete_channel_not_found(client):
    """Test deleting a non-existing channel returns 404."""
    res = client.delete("/api/channels/99999")
    assert res.status_code == 404


def test_post_scrape_success(client, monkeypatch):
    """Test POST /api/scrape collects posts and returns summary."""
    client.post("/api/channels", json={"username": "test_scrape_chan"})

    sample_html = """
    <div class="tgme_widget_message">
        <a class="tgme_widget_message_date" href="https://t.me/test_scrape_chan/10"></a>
        <div class="tgme_widget_message_text">پست نمونه از کانال</div>
    </div>
    """

    class MockResp:
        is_success = True
        status_code = 200
        text = sample_html

        def raise_for_status(self):
            pass

    monkeypatch.setattr("telegram_ai_content_manager.services.scraper.httpx.get", lambda *args, **kwargs: MockResp())

    res = client.post("/api/scrape")
    assert res.status_code == 200
    assert res.json["channels"] == 1
    assert res.json["new"] == 1
    assert res.json["errors"] == []


def test_post_scrape_error_handling(client, monkeypatch):
    """Test POST /api/scrape records errors when channel fetch fails."""
    client.post("/api/channels", json={"username": "fail_chan"})

    def mock_get_fail(*args, **kwargs):
        raise ValueError("Network timeout simulated")

    monkeypatch.setattr("telegram_ai_content_manager.services.scraper.httpx.get", mock_get_fail)
    res = client.post("/api/scrape")
    assert res.status_code == 200
    assert len(res.json["errors"]) == 1
    assert "Network timeout simulated" in res.json["errors"][0]


def test_get_source_posts(client, monkeypatch):
    """Test GET /api/source-posts returns scraped text posts."""
    client.post("/api/channels", json={"username": "posts_chan"})

    sample_html = """
    <div class="tgme_widget_message">
        <a class="tgme_widget_message_date" href="https://t.me/posts_chan/1"></a>
        <div class="tgme_widget_message_text">پست آزمایشی</div>
    </div>
    """

    class MockResp:
        is_success = True
        status_code = 200
        text = sample_html

        def raise_for_status(self):
            pass

    monkeypatch.setattr("telegram_ai_content_manager.services.scraper.httpx.get", lambda *args, **kwargs: MockResp())
    client.post("/api/scrape")

    res = client.get("/api/source-posts")
    assert res.status_code == 200
    assert len(res.json) == 1
    assert res.json[0]["text"] == "پست آزمایشی"
    assert res.json[0]["channel"] == "posts_chan"


def test_post_draft_direct_success(client):
    """Test POST /api/drafts/direct creates manual draft."""
    res = client.post("/api/drafts/direct", json={"text": "متن پیش‌نویس مستقیم"})
    assert res.status_code == 201
    assert res.json["text"] == "متن پیش‌نویس مستقیم"
    assert res.json["status"] == "draft"


def test_post_draft_direct_invalid(client):
    """Test POST /api/drafts/direct with empty text returns 400."""
    res = client.post("/api/drafts/direct", json={"text": "   "})
    assert res.status_code == 400
    assert "error" in res.json


def test_post_draft_random_empty(client):
    """Test POST /api/drafts/random returns 400 when no text posts exist."""
    res = client.post("/api/drafts/random")
    assert res.status_code == 400
    assert "No text posts are available" in res.json["error"]


def test_post_draft_random_success(client, monkeypatch):
    """Test POST /api/drafts/random creates a draft from a saved post."""
    client.post("/api/channels", json={"username": "rand_chan"})

    sample_html = """
    <div class="tgme_widget_message">
        <a class="tgme_widget_message_date" href="https://t.me/rand_chan/20"></a>
        <div class="tgme_widget_message_text">متن پست برای انتخاب تصادفی</div>
    </div>
    """

    class MockResp:
        is_success = True
        status_code = 200
        text = sample_html

        def raise_for_status(self):
            pass

    monkeypatch.setattr("telegram_ai_content_manager.services.scraper.httpx.get", lambda *args, **kwargs: MockResp())
    client.post("/api/scrape")

    res = client.post("/api/drafts/random")
    assert res.status_code == 201
    assert res.json["text"] == "متن پست برای انتخاب تصادفی"


def test_post_draft_generate_success(client, monkeypatch):
    """Test POST /api/drafts/generate creates an AI draft."""
    class MockAiResp:
        is_success = True
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "متن تولیدشده با جمینای"}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    monkeypatch.setenv("GEMINI_MODELS", "gemini-3.6-flash")
    monkeypatch.setattr("telegram_ai_content_manager.services.ai.httpx.post", lambda *args, **kwargs: MockAiResp())

    res = client.post("/api/drafts/generate", json={"topic": "تست فناوری", "model": "gemini-3.6-flash"})
    assert res.status_code == 201
    assert res.json["text"] == "متن تولیدشده با جمینای"


def test_post_draft_generate_error(client, monkeypatch):
    """Test POST /api/drafts/generate without API key returns 400."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = client.post("/api/drafts/generate", json={"topic": "تست", "model": "gemini-3.6-flash"})
    assert res.status_code == 400
    assert "GEMINI_API_KEY must be configured" in res.json["error"]


def test_patch_draft_success(client):
    """Test PATCH /api/drafts/<id> edits unpublished draft."""
    dir_res = client.post("/api/drafts/direct", json={"text": "متن اولیه"})
    draft_id = dir_res.json["id"]

    patch_res = client.patch(f"/api/drafts/{draft_id}", json={"text": "متن ویرایش شده"})
    assert patch_res.status_code == 200
    assert patch_res.json["text"] == "متن ویرایش شده"


def test_post_draft_publish_success(client, monkeypatch):
    """Test POST /api/drafts/<id>/publish publishes draft to Telegram."""
    dir_res = client.post("/api/drafts/direct", json={"text": "پست آماده انتشار"})
    draft_id = dir_res.json["id"]

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@fake_target")

    class MockTgResp:
        is_success = True
        status_code = 200

        def json(self):
            return {"ok": True, "result": {"message_id": 4321}}

    monkeypatch.setattr(
        "telegram_ai_content_manager.services.drafts.httpx.post",
        lambda *args, **kwargs: MockTgResp(),
    )

    pub_res = client.post(f"/api/drafts/{draft_id}/publish")
    assert pub_res.status_code == 200
    assert pub_res.json["status"] == "published"
    assert pub_res.json["published_at"] is not None


def test_patch_draft_published_error(client, monkeypatch):
    """Test PATCH /api/drafts/<id> on published draft returns 409 Conflict."""
    dir_res = client.post("/api/drafts/direct", json={"text": "پست برای انتشار"})
    draft_id = dir_res.json["id"]

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@fake_target")

    class MockTgResp:
        is_success = True
        status_code = 200

        def json(self):
            return {"ok": True, "result": {"message_id": 4321}}

    monkeypatch.setattr(
        "telegram_ai_content_manager.services.drafts.httpx.post",
        lambda *args, **kwargs: MockTgResp(),
    )
    client.post(f"/api/drafts/{draft_id}/publish")

    patch_res = client.patch(f"/api/drafts/{draft_id}", json={"text": "ویرایش غیرمجاز"})
    assert patch_res.status_code == 409
    assert "Published drafts cannot be changed" in patch_res.json["error"]


def test_post_draft_publish_already_published_error(client, monkeypatch):
    """Test POST /api/drafts/<id>/publish on already published draft returns 400."""
    dir_res = client.post("/api/drafts/direct", json={"text": "پست برای انتشار مجدد"})
    draft_id = dir_res.json["id"]

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@fake_target")

    class MockTgResp:
        is_success = True
        status_code = 200

        def json(self):
            return {"ok": True, "result": {"message_id": 4321}}

    monkeypatch.setattr(
        "telegram_ai_content_manager.services.drafts.httpx.post",
        lambda *args, **kwargs: MockTgResp(),
    )
    client.post(f"/api/drafts/{draft_id}/publish")

    pub2_res = client.post(f"/api/drafts/{draft_id}/publish")
    assert pub2_res.status_code == 400
    assert "already been published" in pub2_res.json["error"]
