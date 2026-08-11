"""JSON REST API routes for dashboard and automation."""

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import desc

from ..config import get_configured_models
from ..models import Draft, SourceChannel, SourcePost, db
from ..services import (
    create_direct_draft,
    create_random_draft,
    generate_with_gemini,
    normalize_channel,
    publish_draft,
    run_scrape,
    source_candidates,
    validate_text,
)

api = Blueprint("api", __name__)


def draft_payload(draft: Draft) -> dict:
    """Serialize a Draft instance for API responses."""
    return {
        "id": draft.id,
        "text": draft.text,
        "status": draft.status,
        "created_at": draft.created_at.isoformat(),
        "published_at": draft.published_at.isoformat() if draft.published_at else None,
        "source_url": draft.source_post.url if draft.source_post else None,
    }


def channel_payload(channel: SourceChannel) -> dict:
    """Serialize a SourceChannel instance for API responses."""
    return {
        "id": channel.id,
        "username": channel.username,
        "enabled": channel.enabled,
        "last_scraped_at": channel.last_scraped_at.isoformat() if channel.last_scraped_at else None,
        "posts_count": len(channel.posts) if channel.posts is not None else 0,
    }


def error(message: str, status: int = 400):
    """Return a JSON error response."""
    return jsonify({"error": message}), status


def request_json() -> dict:
    """Safely extract JSON body from request."""
    return request.get_json(silent=True) or {}


@api.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@api.get("/api/dashboard")
def dashboard_data():
    """Return dashboard statistics and recent drafts."""
    return jsonify(
        {
            "channels": SourceChannel.query.count(),
            "posts": SourcePost.query.count(),
            "drafts": Draft.query.filter_by(status="draft").count(),
            "published": Draft.query.filter_by(status="published").count(),
            "recent_drafts": [
                draft_payload(item) for item in Draft.query.order_by(desc(Draft.created_at)).limit(8)
            ],
        }
    )


@api.get("/api/models")
def ai_models():
    """Return enabled AI models for the frontend studio."""
    models = get_configured_models()
    default_model = models[0]["id"] if models else "gemini-3.6-flash"
    return jsonify({"models": models, "default_model": default_model})


@api.route("/api/channels", methods=["GET", "POST"])
def channels():
    """List enabled channels or add a new Telegram channel."""
    if request.method == "GET":
        return jsonify(
            [channel_payload(item) for item in SourceChannel.query.order_by(SourceChannel.username)]
        )
    try:
        username = normalize_channel(request_json().get("username"))
    except ValueError as exc:
        return error(str(exc))
    if SourceChannel.query.filter_by(username=username).first():
        return error("Channel already exists.", 409)
    channel = SourceChannel(username=username)
    db.session.add(channel)
    db.session.commit()
    return jsonify(channel_payload(channel)), 201


@api.delete("/api/channels/<int:channel_id>")
def remove_channel(channel_id: int):
    """Delete a tracked channel and its scraped posts."""
    channel = db.get_or_404(SourceChannel, channel_id)
    db.session.delete(channel)
    db.session.commit()
    return "", 204


@api.post("/api/scrape")
def scrape():
    """Run scraper across all enabled channels."""
    try:
        return jsonify(
            run_scrape(
                current_app.config.get("SCRAPER_LIMIT", 10),
                current_app.config.get("SCRAPER_TIMEOUT", 20.0),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Scrape failed")
        return error(str(exc), 500)


@api.get("/api/source-posts")
def source_posts():
    """List candidate source posts with text."""
    return jsonify(
        [
            {
                "id": item.id,
                "channel": item.channel.username if item.channel else "unknown",
                "text": item.text,
                "url": item.url,
            }
            for item in source_candidates()
        ]
    )


@api.get("/api/drafts")
def drafts():
    """List recent drafts."""
    return jsonify([draft_payload(item) for item in Draft.query.order_by(desc(Draft.created_at)).limit(30)])


@api.post("/api/drafts/direct")
def direct_draft():
    """Create a manual draft from user input."""
    try:
        return jsonify(draft_payload(create_direct_draft(request_json().get("text")))), 201
    except ValueError as exc:
        return error(str(exc))


@api.post("/api/drafts/random")
def random_draft():
    """Create a draft from a randomly selected scraped post."""
    try:
        return jsonify(draft_payload(create_random_draft())), 201
    except ValueError as exc:
        return error(str(exc))


@api.post("/api/drafts/generate")
def generated_draft():
    """Generate a draft using Gemini or Gemma AI models."""
    data = request_json()
    try:
        draft = generate_with_gemini(
            data.get("topic"),
            data.get("model"),
            data.get("source_post_ids", []),
            data.get("tone", "professional"),
            data.get("length", "medium"),
        )
        return jsonify(draft_payload(draft)), 201
    except ValueError as exc:
        return error(str(exc))


@api.patch("/api/drafts/<int:draft_id>")
def update_draft(draft_id: int):
    """Edit the text of an unpublished draft."""
    draft = db.get_or_404(Draft, draft_id)
    if draft.status == "published":
        return error("Published drafts cannot be changed.", 409)
    try:
        draft.text = validate_text(request_json().get("text"))
    except ValueError as exc:
        return error(str(exc))
    db.session.commit()
    return jsonify(draft_payload(draft))


@api.post("/api/drafts/<int:draft_id>/publish")
def send_draft(draft_id: int):
    """Publish a draft to the Telegram target channel."""
    try:
        return jsonify(draft_payload(publish_draft(db.get_or_404(Draft, draft_id))))
    except ValueError as exc:
        return error(str(exc))
