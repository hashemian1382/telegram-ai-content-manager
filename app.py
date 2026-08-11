"""Single application entry point.

Development:  python app.py        (or: flask run, or: ./start.sh)
Production:   gunicorn app:app
"""

from telegram_ai_content_manager import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
