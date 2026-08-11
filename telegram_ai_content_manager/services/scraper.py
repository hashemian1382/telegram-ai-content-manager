"""Channel scraping and Telegram public preview collector."""

import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func

from ..models import ScrapeRun, SourceChannel, SourcePost, db, utcnow

CHANNEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TelegramAIContentManager/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}


def normalize_channel(value: str | None) -> str:
    """Normalize a channel reference (URL, @handle, or bare name) to a username."""
    value = (value or "").strip()
    value = re.sub(r"^https?://(?:www\.)?t\.me/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^t\.me/", "", value, flags=re.IGNORECASE)
    value = value.lstrip("@").split("/")[0].split("?")[0].strip()
    if not CHANNEL_RE.fullmatch(value):
        raise ValueError("Channel must be a valid public Telegram username.")
    return value


def parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string safely."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def scrape_channel(username: str, limit: int = 10, timeout: float = 20) -> list[dict]:
    """Fetch the latest public posts of a channel via Telegram's web preview."""
    url = f"https://t.me/s/{username}"
    response = httpx.get(url, headers=HTTP_HEADERS, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    records = []
    for widget in soup.select("div.tgme_widget_message")[-limit:]:
        link = widget.select_one("a.tgme_widget_message_date")
        if not link or not link.get("href"):
            continue
        post_url = link["href"].split("?")[0]
        match = re.search(r"/(\d+)$", post_url)
        if not match:
            continue
        text_node = widget.select_one("div.tgme_widget_message_text")
        time_node = widget.select_one("time")
        records.append(
            {
                "telegram_post_id": int(match.group(1)),
                "url": post_url,
                "text": text_node.get_text("\n", strip=True) if text_node else "",
                "published_at": parse_datetime(time_node.get("datetime", "") if time_node else ""),
                "has_media": bool(
                    widget.select_one(".tgme_widget_message_photo, video, .tgme_widget_message_document")
                ),
            }
        )
    return records


def run_scrape(limit: int = 10, timeout: float = 20) -> dict:
    """Collect the latest posts from every enabled source channel."""
    channels = SourceChannel.query.filter_by(enabled=True).order_by(SourceChannel.username).all()
    run = ScrapeRun(channels_count=len(channels))
    db.session.add(run)
    db.session.commit()
    errors, found, inserted = [], 0, 0
    for channel in channels:
        try:
            posts = scrape_channel(channel.username, limit, timeout)
            found += len(posts)
            for item in posts:
                post = SourcePost.query.filter_by(
                    channel_id=channel.id, telegram_post_id=item["telegram_post_id"]
                ).first()
                if post is None:
                    db.session.add(SourcePost(channel_id=channel.id, **item))
                    inserted += 1
                else:
                    post.url = item["url"]
                    post.text = item["text"]
                    post.published_at = item["published_at"]
                    post.has_media = item["has_media"]
                    post.scraped_at = utcnow()
            channel.last_scraped_at = utcnow()
            db.session.commit()
        except (httpx.HTTPError, ValueError) as exc:
            db.session.rollback()
            errors.append(f"@{channel.username}: {exc}")
    run.completed_at = utcnow()
    run.posts_found = found
    run.posts_new = inserted
    run.errors = "\n".join(errors) or None
    db.session.commit()
    return {"channels": len(channels), "found": found, "new": inserted, "errors": errors}


def source_candidates(limit: int = 60) -> list[SourcePost]:
    """Return recent source posts that contain usable text."""
    return (
        SourcePost.query.filter(func.length(SourcePost.text) > 0)
        .order_by(SourcePost.scraped_at.desc())
        .limit(limit)
        .all()
    )
