"""Database setup and SQLAlchemy models."""

from datetime import UTC, datetime
from typing import Any

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class SourceChannel(db.Model):
    """A Telegram public channel tracked for scraping."""

    __tablename__ = "source_channels"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_scraped_at = db.Column(db.DateTime(timezone=True))
    posts = db.relationship("SourcePost", back_populates="channel", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "enabled": self.enabled,
            "last_scraped_at": self.last_scraped_at.isoformat() if self.last_scraped_at else None,
            "posts_count": len(self.posts) if self.posts is not None else 0,
        }

    def __repr__(self) -> str:
        return f"<SourceChannel id={self.id} username='@{self.username}'>"


class SourcePost(db.Model):
    """A single post scraped from a source channel."""

    __tablename__ = "source_posts"
    __table_args__ = (db.UniqueConstraint("channel_id", "telegram_post_id", name="uq_source_post"),)

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(
        db.Integer, db.ForeignKey("source_channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    telegram_post_id = db.Column(db.BigInteger, nullable=False)
    url = db.Column(db.String(512), nullable=False)
    published_at = db.Column(db.DateTime(timezone=True))
    text = db.Column(db.Text, nullable=False, default="")
    has_media = db.Column(db.Boolean, nullable=False, default=False)
    scraped_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    channel = db.relationship("SourceChannel", back_populates="posts")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "channel": self.channel.username if self.channel else None,
            "telegram_post_id": self.telegram_post_id,
            "url": self.url,
            "text": self.text,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "has_media": self.has_media,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }

    def __repr__(self) -> str:
        return f"<SourcePost id={self.id} url='{self.url}'>"


class Draft(db.Model):
    """A candidate post (direct, random, or AI-generated) before or after publishing."""

    __tablename__ = "drafts"

    id = db.Column(db.Integer, primary_key=True)
    source_post_id = db.Column(db.Integer, db.ForeignKey("source_posts.id", ondelete="SET NULL"))
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    telegram_message_id = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    published_at = db.Column(db.DateTime(timezone=True))
    source_post = db.relationship("SourcePost")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status,
            "telegram_message_id": self.telegram_message_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "source_url": self.source_post.url if self.source_post else None,
            "source_post_id": self.source_post_id,
        }

    def __repr__(self) -> str:
        return f"<Draft id={self.id} status='{self.status}'>"


class ScrapeRun(db.Model):
    """An execution history log for scraping sessions."""

    __tablename__ = "scrape_runs"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime(timezone=True))
    channels_count = db.Column(db.Integer, nullable=False, default=0)
    posts_found = db.Column(db.Integer, nullable=False, default=0)
    posts_new = db.Column(db.Integer, nullable=False, default=0)
    errors = db.Column(db.Text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "channels": self.channels_count,
            "found": self.posts_found,
            "new": self.posts_new,
            "errors": [item for item in self.errors.split("\n") if item] if self.errors else [],
        }

    def __repr__(self) -> str:
        return f"<ScrapeRun id={self.id} new={self.posts_new}>"
