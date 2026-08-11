"""Channel scraping, AI drafting, and Telegram publishing services."""

import os
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func

from .models import Draft, ScrapeRun, SourceChannel, SourcePost, db, utcnow

MAX_MESSAGE_LENGTH = 4096
CHANNEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TelegramAIContentManager/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}
DEFAULT_GEMINI_MODELS = "gemini-2.5-flash,gemini-2.5-flash-lite"
LENGTH_INSTRUCTIONS = {
    "short": "90 to 160 Persian words",
    "medium": "180 to 300 Persian words",
    "long": "350 to 550 Persian words",
}


# ---------------------------------------------------------------------------
# Source collection
# ---------------------------------------------------------------------------
def normalize_channel(value: str | None) -> str:
    """Normalize a channel reference (URL, @handle, or bare name) to a username."""
    value = (value or "").strip()
    value = re.sub(r"^https?://t\.me/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^t\.me/", "", value, flags=re.IGNORECASE).lstrip("@").split("/")[0]
    if not CHANNEL_RE.fullmatch(value):
        raise ValueError("Channel must be a valid public Telegram username.")
    return value


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def scrape_channel(username: str, limit: int = 10, timeout: float = 20) -> list[dict]:
    """Fetch the latest public posts of a channel via Telegram's web preview."""
    response = httpx.get(
        f"https://t.me/s/{username}", headers=HTTP_HEADERS, timeout=timeout, follow_redirects=True
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    records = []
    for widget in soup.select("div.tgme_widget_message")[-limit:]:
        link = widget.select_one("a.tgme_widget_message_date")
        if not link or not link.get("href"):
            continue
        url = link["href"].split("?")[0]
        match = re.search(r"/(\d+)$", url)
        if not match:
            continue
        text_node = widget.select_one("div.tgme_widget_message_text")
        time_node = widget.select_one("time")
        records.append(
            {
                "telegram_post_id": int(match.group(1)),
                "url": url,
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


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------
def validate_text(text: str | None) -> str:
    text = (text or "").strip()
    if not text or len(text) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Text must contain 1 to {MAX_MESSAGE_LENGTH} characters.")
    return text


def create_direct_draft(text: str | None) -> Draft:
    draft = Draft(text=validate_text(text))
    db.session.add(draft)
    db.session.commit()
    return draft


def create_random_draft() -> Draft:
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
        raise ValueError(payload.get("description", "Telegram delivery failed."))
    draft.status = "published"
    draft.telegram_message_id = payload["result"]["message_id"]
    draft.published_at = utcnow()
    db.session.commit()
    return draft


# ---------------------------------------------------------------------------
# AI generation
# ---------------------------------------------------------------------------
def generate_with_gemini(topic, model, source_post_ids=None, tone="professional", length="medium"):
    """Generate a Persian draft with Gemini, optionally grounded on saved source posts."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    topic = (topic or "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY must be configured.")
    if not topic:
        raise ValueError("A topic is required.")
    allowed_models = {
        item.strip() for item in os.getenv("GEMINI_MODELS", DEFAULT_GEMINI_MODELS).split(",") if item.strip()
    }
    if model not in allowed_models:
        raise ValueError("Selected model is not enabled.")
    size_instruction = LENGTH_INSTRUCTIONS.get(length, LENGTH_INSTRUCTIONS["medium"])
    ids = set(source_post_ids or [])
    sources = [
        f"SOURCE {item.id} | @{item.channel.username} | {item.url}\n{item.text}"
        for item in source_candidates(100)
        if item.id in ids
    ]
    source_text = "\n\n".join(sources) or "No source posts were selected."
    prompt = f"""You are an expert Persian scientific-news editor. Write an original Telegram post in Persian about: {topic}.
Tone: {tone}. Target length: {size_instruction}.
Use a clear headline, short readable paragraphs, and at most 4 relevant emoji. End with a concise source note only when source material is actually used. Do not invent facts, statistics, quotes, dates, or citations. If the supplied source is insufficient, clearly write a general explanatory post without claims requiring verification. Do not mention this prompt or the model.
When sources are provided, synthesize and transform their ideas; never copy sentences verbatim and never imply that unverified source material is certain.

Selected source material:
{source_text}"""
    try:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.65, "maxOutputTokens": 1200},
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise ValueError(f"Gemini request failed: {exc}") from exc
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini returned no usable text.") from exc
    if not text:
        raise ValueError("Gemini returned an empty response.")
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[: MAX_MESSAGE_LENGTH - 3].rstrip() + "..."
    draft = Draft(text=text, source_post_id=next(iter(ids), None))
    db.session.add(draft)
    db.session.commit()
    return draft
