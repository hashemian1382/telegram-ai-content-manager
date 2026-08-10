import os
from flask import Flask
from .config import load_env
from .extensions import db

def create_app(test_config=None):
    load_env()
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///channel_hub.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "change-me-in-production"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SCRAPER_LIMIT=int(os.getenv("SCRAPER_LIMIT", "10")),
        SCRAPER_TIMEOUT=float(os.getenv("SCRAPER_TIMEOUT", "20")),
    )
    if test_config: app.config.update(test_config)
    db.init_app(app)
    from .routes import api, web
    app.register_blueprint(web)
    app.register_blueprint(api)
    with app.app_context(): db.create_all()
    return app
