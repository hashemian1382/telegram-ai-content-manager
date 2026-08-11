"""Draft creation and Telegram publishing services."""

import os

import httpx
from sqlalchemy import func

from ..models import Draft, SourcePost, db, utcnow

MAX_MESSAGE_LENGTH = 4096


def validate_text(text: str | None) -> str:
    """Validate and clean message text."""
    text = (text or "").strip()
    if not text or len(text) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Text must contain 1 to {MAX_MESSAGE_LENGTH} characters.")
    return text


def create_direct_draft(text: str | None) -> Draft:
    """Create a new manual draft."""
    draft = Draft(text=validate_text(text))
    db.session.add(draft)
    db.session.commit()
    return draft


def create_random_draft() -> Draft:
    """Select a random scraped post to create a draft."""
    post = SourcePost.query.filter(func.length(SourcePost.text) > 0).order_by(func.random()).first()
    if post is None:
        raise ValueError("No text posts are available. Add channels and run a scrape first.")
    draft = Draft(source_post_id=post.id, text=post.text)
    db.session.add(draft)
    db.session.commit()
    return draft


def publish_draft(draft: Draft) -> Draft:
    """Publish an approved draft to the configured Telegram channel."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not channel:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID must be configured.")
    if draft.status == "published":
        raise ValueError("This draft has already been published.")
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": channel, "text": draft.text},
            timeout=30,
        )
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError(f"Telegram delivery failed: {exc}") from exc
    if not payload.get("ok"):
        err_desc = payload.get("description", "Telegram delivery failed.")
        raise ValueError(f"Telegram error: {err_desc}")
    draft.status = "published"
    draft.telegram_message_id = payload["result"]["message_id"]
    draft.published_at = utcnow()
    db.session.commit()
    return draft
