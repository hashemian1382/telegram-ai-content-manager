"""Production WSGI entry point."""

from telegram_ai_content_manager import create_app

app = create_app()
