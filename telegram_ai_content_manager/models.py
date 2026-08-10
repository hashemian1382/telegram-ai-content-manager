from datetime import UTC, datetime

from .extensions import db


def utcnow():
    return datetime.now(UTC)


class SourceChannel(db.Model):
    __tablename__ = "source_channels"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_scraped_at = db.Column(db.DateTime(timezone=True))
    posts = db.relationship("SourcePost", back_populates="channel", cascade="all, delete-orphan")


class SourcePost(db.Model):
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


class Draft(db.Model):
    __tablename__ = "drafts"
    id = db.Column(db.Integer, primary_key=True)
    source_post_id = db.Column(db.Integer, db.ForeignKey("source_posts.id", ondelete="SET NULL"))
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    telegram_message_id = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    published_at = db.Column(db.DateTime(timezone=True))
    source_post = db.relationship("SourcePost")


class ScrapeRun(db.Model):
    __tablename__ = "scrape_runs"
    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime(timezone=True))
    channels_count = db.Column(db.Integer, nullable=False, default=0)
    posts_found = db.Column(db.Integer, nullable=False, default=0)
    posts_new = db.Column(db.Integer, nullable=False, default=0)
    errors = db.Column(db.Text)
