from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import desc

from .extensions import db
from .models import Draft, SourceChannel, SourcePost
from .services import (
    create_direct_draft,
    create_random_draft,
    generate_with_gemini,
    normalize_channel,
    publish_draft,
    run_scrape,
    source_candidates,
)

api = Blueprint("api", __name__)
web = Blueprint("web", __name__)


def draft_payload(draft):
    return {
        "id": draft.id,
        "text": draft.text,
        "status": draft.status,
        "created_at": draft.created_at.isoformat(),
        "published_at": draft.published_at.isoformat() if draft.published_at else None,
        "source_url": draft.source_post.url if draft.source_post else None,
    }


def channel_payload(channel):
    return {
        "id": channel.id,
        "username": channel.username,
        "enabled": channel.enabled,
        "last_scraped_at": channel.last_scraped_at.isoformat() if channel.last_scraped_at else None,
        "posts_count": len(channel.posts),
    }


def error(message, status=400):
    return jsonify({"error": message}), status


@web.get("/")
def dashboard():
    return render_template("index.html")


@api.get("/health")
def health():
    return {"status": "ok"}


@api.get("/api/dashboard")
def dashboard_data():
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


@api.route("/api/channels", methods=["GET", "POST"])
def channels():
    if request.method == "GET":
        return jsonify(
            [channel_payload(item) for item in SourceChannel.query.order_by(SourceChannel.username)]
        )
    try:
        username = normalize_channel((request.get_json(silent=True) or {}).get("username"))
    except ValueError as exc:
        return error(str(exc))
    if SourceChannel.query.filter_by(username=username).first():
        return error("Channel already exists.", 409)
    channel = SourceChannel(username=username)
    db.session.add(channel)
    db.session.commit()
    return jsonify(channel_payload(channel)), 201


@api.delete("/api/channels/<int:channel_id>")
def remove_channel(channel_id):
    channel = db.get_or_404(SourceChannel, channel_id)
    db.session.delete(channel)
    db.session.commit()
    return "", 204


@api.post("/api/scrape")
def scrape():
    try:
        return jsonify(run_scrape(current_app.config["SCRAPER_LIMIT"]))
    except Exception as exc:
        current_app.logger.exception("Scrape failed")
        return error(str(exc), 500)


@api.get("/api/source-posts")
def source_posts():
    return jsonify(
        [
            {"id": item.id, "channel": item.channel.username, "text": item.text, "url": item.url}
            for item in source_candidates()
        ]
    )


@api.get("/api/drafts")
def drafts():
    return jsonify([draft_payload(item) for item in Draft.query.order_by(desc(Draft.created_at)).limit(30)])


@api.post("/api/drafts/direct")
def direct_draft():
    try:
        return jsonify(
            draft_payload(create_direct_draft((request.get_json(silent=True) or {}).get("text")))
        ), 201
    except ValueError as exc:
        return error(str(exc))


@api.post("/api/drafts/random")
def random_draft():
    try:
        return jsonify(draft_payload(create_random_draft())), 201
    except ValueError as exc:
        return error(str(exc))


@api.post("/api/drafts/generate")
def generated_draft():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(
            draft_payload(
                generate_with_gemini(
                    data.get("topic"),
                    data.get("model"),
                    data.get("source_post_ids", []),
                    data.get("tone", "professional"),
                    data.get("length", "medium"),
                )
            )
        ), 201
    except ValueError as exc:
        return error(str(exc))


@api.patch("/api/drafts/<int:draft_id>")
def update_draft(draft_id):
    draft = db.get_or_404(Draft, draft_id)
    text = (request.get_json(silent=True) or {}).get("text", "").strip()
    if draft.status == "published":
        return error("Published drafts cannot be changed.", 409)
    if not text or len(text) > 4096:
        return error("Text must contain 1 to 4096 characters.")
    draft.text = text
    db.session.commit()
    return jsonify(draft_payload(draft))


@api.post("/api/drafts/<int:draft_id>/publish")
def send_draft(draft_id):
    try:
        return jsonify(draft_payload(publish_draft(db.get_or_404(Draft, draft_id))))
    except ValueError as exc:
        return error(str(exc))
