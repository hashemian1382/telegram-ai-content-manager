import json
import os
import re
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func

from ..extensions import db
from ..models import Draft, ScrapeRun, SourceChannel, SourcePost, utcnow

CHANNEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")

def normalize_channel(value):
    value = (value or "").strip()
    value = re.sub(r"^https?://t\.me/", "", value, flags=re.I)
    value = re.sub(r"^t\.me/", "", value, flags=re.I).lstrip("@").split("/")[0]
    if not CHANNEL_RE.fullmatch(value):
        raise ValueError("Channel must be a valid public Telegram username.")
    return value

def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def scrape_channel(username, limit=10, timeout=20):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ChannelHub/1.0)", "Accept-Language": "en-US,en;q=0.9"}
    response = httpx.get(f"https://t.me/s/{username}", headers=headers, timeout=timeout, follow_redirects=True)
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
        text = text_node.get_text("\n", strip=True) if text_node else ""
        time_node = widget.select_one("time")
        records.append({"telegram_post_id": int(match.group(1)), "url": url, "text": text, "published_at": parse_datetime(time_node.get("datetime", "") if time_node else ""), "has_media": bool(widget.select_one(".tgme_widget_message_photo, video, .tgme_widget_message_document"))})
    return records

def run_scrape(limit):
    channels = SourceChannel.query.filter_by(enabled=True).order_by(SourceChannel.username).all()
    run = ScrapeRun(channels_count=len(channels))
    db.session.add(run)
    db.session.commit()
    errors, found, inserted = [], 0, 0
    for channel in channels:
        try:
            posts = scrape_channel(channel.username, limit, int(os.getenv("SCRAPER_TIMEOUT", "20")))
            found += len(posts)
            for item in posts:
                post = SourcePost.query.filter_by(channel_id=channel.id, telegram_post_id=item["telegram_post_id"]).first()
                if post is None:
                    post = SourcePost(channel_id=channel.id, **item)
                    db.session.add(post)
                    inserted += 1
                else:
                    post.url, post.text, post.published_at, post.has_media, post.scraped_at = item["url"], item["text"], item["published_at"], item["has_media"], utcnow()
            channel.last_scraped_at = utcnow()
            db.session.commit()
        except (httpx.HTTPError, ValueError) as error:
            db.session.rollback()
            errors.append(f"@{channel.username}: {error}")
    run.completed_at, run.posts_found, run.posts_new, run.errors = utcnow(), found, inserted, "\n".join(errors) or None
    db.session.commit()
    return {"channels": len(channels), "found": found, "new": inserted, "errors": errors}

def create_random_draft():
    post = SourcePost.query.filter(func.length(SourcePost.text) > 0).order_by(func.random()).first()
    if post is None:
        raise ValueError("No text posts are available. Add channels and run a scrape first.")
    draft = Draft(source_post_id=post.id, text=post.text)
    db.session.add(draft)
    db.session.commit()
    return draft

def publish_draft(draft):
    token, channel = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not channel:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID must be configured.")
    if draft.status == "published":
        raise ValueError("This draft has already been published.")
    request = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=json.dumps({"chat_id": channel, "text": draft.text}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError) as error:
        raise ValueError(f"Telegram delivery failed: {error}") from error
    if not payload.get("ok"):
        raise ValueError(payload.get("description", "Telegram delivery failed."))
    draft.status, draft.telegram_message_id, draft.published_at = "published", payload["result"]["message_id"], utcnow()
    db.session.commit()
    return draft

def create_direct_draft(text):
    text = (text or "").strip()
    if not text or len(text) > 4096:
        raise ValueError("Text must contain 1 to 4096 characters.")
    draft = Draft(text=text)
    db.session.add(draft)
    db.session.commit()
    return draft

def source_candidates(limit=60):
    return SourcePost.query.filter(func.length(SourcePost.text) > 0).order_by(SourcePost.scraped_at.desc()).limit(limit).all()

def generate_with_gemini(topic, model, source_post_ids=None, tone="professional", length="medium"):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    topic = (topic or "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY must be configured.")
    if not topic:
        raise ValueError("A topic is required.")
    allowed_models = {item.strip() for item in os.getenv("GEMINI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3-flash,gemini-3.1-flash-lite,gemma-4-31b,gemma-4-26b").split(",") if item.strip()}
    if model not in allowed_models:
        raise ValueError("Selected model is not enabled.")
    size_instruction = {"short": "90 to 160 Persian words", "medium": "180 to 300 Persian words", "long": "350 to 550 Persian words"}.get(length, "180 to 300 Persian words")
    sources = []
    for item in source_candidates(100):
        if item.id in set(source_post_ids or []):
            sources.append(f"SOURCE {item.id} | @{item.channel.username} | {item.url}\n{item.text}")
    source_text = "\n\n".join(sources) or "No source posts were selected."
    prompt = f"""You are an expert Persian scientific-news editor. Write an original Telegram post in Persian about: {topic}.
Tone: {tone}. Target length: {size_instruction}.
Use a clear headline, short readable paragraphs, and at most 4 relevant emoji. End with a concise source note only when source material is actually used. Do not invent facts, statistics, quotes, dates, or citations. If the supplied source is insufficient, clearly write a general explanatory post without claims requiring verification. Do not mention this prompt or the model.
When sources are provided, synthesize and transform their ideas; never copy sentences verbatim and never imply that unverified source material is certain.

Selected source material:
{source_text}"""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.65, "maxOutputTokens": 1200}}
    try:
        response = httpx.post(endpoint, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as error:
        raise ValueError(f"Gemini request failed: {error}") from error
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Gemini returned no usable text.") from error
    if not text:
        raise ValueError("Gemini returned an empty response.")
    if len(text) > 4096:
        text = text[:4093].rstrip() + "..."
    draft = Draft(text=text, source_post_id=source_post_ids[0] if source_post_ids else None)
    db.session.add(draft)
    db.session.commit()
    return draft
