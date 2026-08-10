import pytest

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.extensions import db
from telegram_ai_content_manager.models import SourceChannel, SourcePost


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "SECRET_KEY": "test"})
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app.test_client()


def test_health_and_direct_draft(client):
    assert client.get("/health").status_code == 200
    response = client.post("/api/drafts/direct", json={"text": "متن آزمایشی"})
    assert response.status_code == 201
    assert response.json["status"] == "draft"


def test_add_channel(client):
    assert client.post("/api/channels", json={"username": "sample_channel"}).status_code == 201
    assert client.post("/api/channels", json={"username": "sample_channel"}).status_code == 409


def test_gemini_draft_is_persisted(client, monkeypatch):
    with client.application.app_context():
        channel = SourceChannel(username="sample_channel")
        db.session.add(channel)
        db.session.commit()
        db.session.add(
            SourcePost(
                channel_id=channel.id, telegram_post_id=1, url="https://t.me/sample_channel/1", text="source"
            )
        )
        db.session.commit()

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "پست تولیدشده"}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "telegram_ai_content_manager.services.content.httpx.post", lambda *args, **kwargs: Response()
    )
    response = client.post(
        "/api/drafts/generate", json={"topic": "علم", "model": "gemini-2.5-flash", "source_post_ids": [1]}
    )
    assert response.status_code == 201
    assert response.json["text"] == "پست تولیدشده"
