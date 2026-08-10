# Channel Hub

A production-minded Telegram content workspace. It collects public-channel posts into a SQL database, lets an editor write or generate drafts, and publishes only after an explicit approval action.

## Features

- Public source-channel registry and text/metadata collection
- SQLite by default; PostgreSQL, Neon, Supabase, Render PostgreSQL, and other SQLAlchemy URLs through one `DATABASE_URL` variable
- Direct drafting, random source selection, and Gemini-assisted Persian drafts
- Optional selected-source context for AI, with original-synthesis guardrails
- Editable drafts and an explicit, one-time Telegram publish operation
- Persian RTL dashboard, JSON API, health endpoint, tests, Docker-free Render configuration, and GitHub Actions CI

## Quick start

```bash
git clone <your-repository-url>
cd channel-hub
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python run.py
```

Visit `http://localhost:5000`.

## Configuration

Create `.env` from `.env.example`. Do not commit it.

```env
SECRET_KEY=use-a-long-random-value
DATABASE_URL=sqlite:///channel_hub.db
TELEGRAM_BOT_TOKEN=your-current-bot-token
TELEGRAM_CHANNEL_ID=@your_channel
GEMINI_API_KEY=your-gemini-key
GEMINI_MODELS=gemini-3.5-flash,gemini-3.5-flash-lite
SCRAPER_LIMIT=10
SCRAPER_TIMEOUT=20
```

For Neon or any PostgreSQL provider, only replace `DATABASE_URL`, for example:

```env
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
```

The application normalizes `postgres://` and `postgresql://` URLs to the installed Psycopg 3 driver automatically.

## Commands

```bash
python run.py
pytest -q
ruff check .
gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 2 --timeout 120
```

## Deploying to Render

`render.yaml` provisions a Web Service and PostgreSQL database. Add the secret environment variables in the Render dashboard: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, and `GEMINI_API_KEY`. Render injects `DATABASE_URL` and generates `SECRET_KEY` from the blueprint. The `Procfile` is included for manual setup.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Deployment health check |
| GET/POST | `/api/channels` | List/add source channels |
| DELETE | `/api/channels/<id>` | Delete a source channel and its posts |
| POST | `/api/scrape` | Collect current source posts |
| GET | `/api/source-posts` | List source posts for AI context |
| POST | `/api/drafts/direct` | Create a manual draft |
| POST | `/api/drafts/random` | Create a random-source draft |
| POST | `/api/drafts/generate` | Create a Gemini draft |
| GET | `/api/drafts` | List recent drafts |
| PATCH | `/api/drafts/<id>` | Edit an unpublished draft |
| POST | `/api/drafts/<id>/publish` | Publish an approved draft |

## Security and editorial policy

Use newly rotated credentials; never place keys in Git, browser code, logs, or issue trackers. Publishing is deliberately not automatic. Only collect public channels you may monitor, respect rights holders and platform terms, and review AI output for accuracy and attribution before publishing.

## Repository layout

```text
channelhub/            Flask application package
  services/            Collection, AI generation, drafting, publishing
tests/                 Fast, external-call-free tests
wsgi.py                Production entry point
run.py                 Local development entry point
render.yaml            Render blueprint
pyproject.toml         Packaging, dependencies, test and lint configuration
```
