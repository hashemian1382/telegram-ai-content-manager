"""Telegram AI Content Manager application factory."""

import os

from flask import Flask

from .config import Config, database_url, load_env
from .extensions import db


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the web application."""
    load_env()
    app = Flask(__name__)
    app.config.from_object(Config)
    # Config is evaluated at import time; refresh values after loading .env.
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "change-me-in-production"),
        SQLALCHEMY_DATABASE_URI=database_url(),
        SCRAPER_LIMIT=int(os.getenv("SCRAPER_LIMIT", "10")),
        SCRAPER_TIMEOUT=float(os.getenv("SCRAPER_TIMEOUT", "20")),
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from .routes import api, web

    app.register_blueprint(web)
    app.register_blueprint(api)

    with app.app_context():
        db.create_all()

    return app
