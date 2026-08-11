"""AI content generation service using Google Gemini and Gemma models."""

import os

import httpx

from ..config import DEFAULT_GEMINI_MODELS
from ..models import Draft, db
from .drafts import MAX_MESSAGE_LENGTH
from .scraper import source_candidates

LENGTH_INSTRUCTIONS = {
    "short": "90 to 160 Persian words",
    "medium": "180 to 300 Persian words",
    "long": "350 to 550 Persian words",
}


def get_allowed_model_ids() -> set[str]:
    """Return a set of lowercase model IDs allowed by environment configuration."""
    raw = os.getenv("GEMINI_MODELS", DEFAULT_GEMINI_MODELS)
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def generate_with_gemini(
    topic: str | None,
    model: str | None,
    source_post_ids: list[int] | None = None,
    tone: str = "professional",
    length: str = "medium",
) -> Draft:
    """Generate a Persian draft with Gemini/Gemma, optionally grounded on saved source posts."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    topic = (topic or "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY must be configured.")
    if not topic:
        raise ValueError("A topic is required.")

    model_id = (model or "").strip().lower()
    allowed_models = get_allowed_model_ids()
    if model_id not in allowed_models:
        raise ValueError(f"Selected model '{model}' is not enabled.")

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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    try:
        response = httpx.post(
            url,
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.65, "maxOutputTokens": 1200},
            },
            timeout=60,
        )
        if not response.is_success:
            err_msg = f"HTTP {response.status_code}"
            try:
                data_err = response.json()
                if isinstance(data_err, dict) and "error" in data_err and "message" in data_err["error"]:
                    err_msg = str(data_err["error"]["message"])
            except (ValueError, TypeError, KeyError):
                err_msg = f"HTTP {response.status_code}"
            raise ValueError(f"Gemini API request failed ({err_msg})")
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
