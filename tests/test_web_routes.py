"""Unit tests for web dashboard routes and HTML rendering."""

import pytest

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.models import db


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
    return app.test_client()


def test_dashboard_page_renders(client):
    """Test that GET / renders the main RTL Persian HTML workspace."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Telegram AI Content Manager" in html
    assert 'dir="rtl"' in html
    assert 'id="scrapeBtn"' in html
    assert "/static/app.js" in html
    assert "/static/app.css" in html
