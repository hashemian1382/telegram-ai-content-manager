"""Unit tests for SQLAlchemy models, cascade deletion, unique constraints, and serialization."""

import pytest
from sqlalchemy.exc import IntegrityError

from telegram_ai_content_manager import create_app
from telegram_ai_content_manager.models import Draft, ScrapeRun, SourceChannel, SourcePost, db


@pytest.fixture
def app_context():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_source_channel_and_post_cascade(app_context):
    """Test channel-post relationship and cascade deletion."""
    channel = SourceChannel(username="test_channel")
    db.session.add(channel)
    db.session.commit()

    post = SourcePost(
        channel_id=channel.id,
        telegram_post_id=101,
        url="https://t.me/test_channel/101",
        text="متن تست",
    )
    db.session.add(post)
    db.session.commit()

    assert len(channel.posts) == 1
    assert repr(channel) == f"<SourceChannel id={channel.id} username='@test_channel'>"
    assert repr(post) == f"<SourcePost id={post.id} url='https://t.me/test_channel/101'>"

    # Test serialization
    c_data = channel.to_dict()
    assert c_data["username"] == "test_channel"
    assert c_data["posts_count"] == 1

    p_data = post.to_dict()
    assert p_data["telegram_post_id"] == 101
    assert p_data["channel"] == "test_channel"

    # Test cascade deletion
    db.session.delete(channel)
    db.session.commit()
    assert SourcePost.query.count() == 0


def test_source_post_unique_constraint(app_context):
    """Test that duplicate post ids in the same channel raise IntegrityError."""
    channel = SourceChannel(username="unique_chan")
    db.session.add(channel)
    db.session.commit()

    post1 = SourcePost(channel_id=channel.id, telegram_post_id=5, url="https://t.me/unique_chan/5", text="a")
    db.session.add(post1)
    db.session.commit()

    post2 = SourcePost(channel_id=channel.id, telegram_post_id=5, url="https://t.me/unique_chan/5", text="b")
    db.session.add(post2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_draft_lifecycle_and_serialization(app_context):
    """Test creating drafts, status changes, and to_dict format."""
    draft = Draft(text="پیش‌نویس نمونه", status="draft")
    db.session.add(draft)
    db.session.commit()

    assert repr(draft) == f"<Draft id={draft.id} status='draft'>"
    d_dict = draft.to_dict()
    assert d_dict["text"] == "پیش‌نویس نمونه"
    assert d_dict["status"] == "draft"
    assert d_dict["published_at"] is None

    draft.status = "published"
    draft.telegram_message_id = 99
    db.session.commit()
    assert draft.to_dict()["telegram_message_id"] == 99


def test_scrape_run_logging(app_context):
    """Test scrape execution logging model."""
    run = ScrapeRun(channels_count=2, posts_found=20, posts_new=5, errors="err1\nerr2")
    db.session.add(run)
    db.session.commit()

    assert repr(run) == f"<ScrapeRun id={run.id} new=5>"
    r_dict = run.to_dict()
    assert r_dict["channels"] == 2
    assert r_dict["found"] == 20
    assert r_dict["new"] == 5
    assert r_dict["errors"] == ["err1", "err2"]
