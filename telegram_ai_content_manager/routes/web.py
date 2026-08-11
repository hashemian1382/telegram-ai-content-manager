"""Web dashboard Blueprint."""

from flask import Blueprint, render_template

web = Blueprint("web", __name__)


@web.get("/")
def dashboard():
    """Render the main Telegram AI Content Manager workspace."""
    return render_template("index.html")
