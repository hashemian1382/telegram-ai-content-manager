"""Unit tests for AI generation service across all 7 Gemini and Gemma models."""

import pytest

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.models import SourceChannel, SourcePost, db
from telegram_ai_content_manager.services.ai import generate_with_gemini, get_allowed_model_ids


@pytest.fixture
def app_context():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_get_allowed_model_ids(monkeypatch):
    """Test that all 7 required models are included in allowed models."""
    monkeypatch.setenv(
        "GEMINI_MODELS",
        "gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b,gemma-4-26b",
    )
    models = get_allowed_model_ids()
    expected = {
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemma-4-31b",
        "gemma-4-26b",
    }
    assert expected.issubset(models)


@pytest.mark.parametrize(
    "model_name",
    [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemma-4-31b",
        "gemma-4-26b",
    ],
)
def test_generate_with_all_gemini_and_gemma_models(app_context, monkeypatch, model_name):
    """Test generating a draft across all 7 required AI models."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-999")
    monkeypatch.setenv(
        "GEMINI_MODELS",
        "gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b,gemma-4-26b",
    )

    channel = SourceChannel(username="ai_test_chan")
    db.session.add(channel)
    db.session.commit()
    post = SourcePost(
        channel_id=channel.id,
        telegram_post_id=7,
        url="https://t.me/ai_test_chan/7",
        text="متن منبع پژوهشی",
    )
    db.session.add(post)
    db.session.commit()

    captured_url = {}

    class MockAiResponse:
        is_success = True
        status_code = 200

        def __init__(self, url):
            captured_url["url"] = url

        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": f"محتوای تولیدشده با {model_name}"}]}}]}

    def mock_post(url, *args, **kwargs):
        return MockAiResponse(url)

    monkeypatch.setattr("telegram_ai_content_manager.services.ai.httpx.post", mock_post)

    draft = generate_with_gemini(
        topic="فناوری کوانتومی",
        model=model_name,
        source_post_ids=[post.id],
        tone="professional",
        length="medium",
    )
    assert draft.id is not None
    assert draft.text == f"محتوای تولیدشده با {model_name}"
    assert draft.source_post_id == post.id
    assert f"/v1beta/models/{model_name}:generateContent" in captured_url["url"]


def test_generate_with_gemini_input_validation(app_context, monkeypatch):
    """Test input validations: API key, topic, and allowed model names."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY must be configured"):
        generate_with_gemini(topic="تست", model="gemini-3.6-flash")

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with pytest.raises(ValueError, match="A topic is required"):
        generate_with_gemini(topic="", model="gemini-3.6-flash")

    with pytest.raises(ValueError, match="not enabled"):
        generate_with_gemini(topic="تست", model="unsupported-gpt-model")


def test_generate_with_gemini_api_error_extraction(app_context, monkeypatch):
    """Test extracting detailed error message from Google API JSON error response."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODELS", "gemini-3.6-flash")

    class MockErrorResponse:
        is_success = False
        status_code = 403

        def json(self):
            return {
                "error": {
                    "code": 403,
                    "message": "Your API key was reported as leaked. Please use another API key.",
                    "status": "PERMISSION_DENIED",
                }
            }

    monkeypatch.setattr("telegram_ai_content_manager.services.ai.httpx.post", lambda *args, **kwargs: MockErrorResponse())

    with pytest.raises(ValueError, match="API key was reported as leaked"):
        generate_with_gemini(topic="تست", model="gemini-3.6-flash")


def test_generate_with_gemini_truncation(app_context, monkeypatch):
    """Test that generated text exceeding 4096 characters is safely truncated."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODELS", "gemini-3.6-flash")

    long_text = "A" * 4500

    class MockLongResponse:
        is_success = True
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": long_text}]}}]}

    monkeypatch.setattr("telegram_ai_content_manager.services.ai.httpx.post", lambda *args, **kwargs: MockLongResponse())

    draft = generate_with_gemini(topic="تست", model="gemini-3.6-flash")
    assert len(draft.text) == 4096
    assert draft.text.endswith("...")
