# Telegram AI Content Manager

A self-hostable workspace for collecting ideas from **public Telegram channels**, creating Persian-language content drafts, reviewing them, and publishing approved drafts to a Telegram channel through a bot.

Built and maintained by **Ali Hashemian**.

> This repository is intentionally designed around editorial control: AI output is saved as a draft first, and a person must explicitly approve publication.

## What is included today

- Register public Telegram source channels and collect their currently accessible posts into a SQL database
- Store source text, post links, timestamps, media flags, and collection-run results
- Write a draft directly, create one from a random saved source post, or generate a Persian draft with Gemini
- Select saved source posts as context for Gemini, then edit every draft before publication
- Publish an approved text draft with the Telegram Bot API
- RTL Persian dashboard, JSON API, health check, tests, GitHub Actions CI, and Render blueprint
- SQLite for local development and PostgreSQL for Render or other hosted environments

## Planned extensions

The project structure keeps room for additional providers and workflows. These are **not implemented in the current version**:

- Tavily or other web-search providers
- Other LLM providers
- Automated schedules, queues, and publish policies
- Media generation and attachment publishing
- Telegram client-based ingestion for channels that cannot be read from the public web preview

## Requirements

- Python 3.11+
- A Telegram bot token and a target channel where that bot is an administrator (only for publishing)
- A Gemini API key (only for AI generation)
- PostgreSQL for production deployments; SQLite is used by default locally

## Run locally

```bash
git clone https://github.com/hashemian1382/telegram-ai-content-manager.git
cd telegram-ai-content-manager
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
cp .env.example .env
python run.py
```

Open [http://localhost:5000](http://localhost:5000). Configure the variables you need in `.env`; never commit that file.

### Environment variables

```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///telegram_ai_content_manager.db

TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHANNEL_ID=@your_channel

GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODELS=gemini-2.5-flash,gemini-2.5-flash-lite

SCRAPER_LIMIT=10
SCRAPER_TIMEOUT=20
```

For PostgreSQL, set a SQLAlchemy-compatible URL. Standard Render/Neon-style `postgres://` and `postgresql://` URLs are normalized automatically for Psycopg 3:

```env
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
```

## Deploy on Render

The included `render.yaml` creates a Web Service and PostgreSQL database.

1. Push this repository to GitHub.
2. In Render, select **New → Blueprint** and choose the repository.
3. Add these secret environment variables to the Web Service: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, and `GEMINI_API_KEY`.
4. Deploy. Render supplies `DATABASE_URL`; the blueprint generates `SECRET_KEY`.

The production command is also available in `Procfile`:

```bash
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

## Development commands

```bash
pytest -q
ruff check .
gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 2 --timeout 120
```

## API

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Deployment health check |
| `GET` / `POST` | `/api/channels` | List or add public source channels |
| `DELETE` | `/api/channels/<id>` | Remove a source channel and its saved posts |
| `POST` | `/api/scrape` | Collect available source posts now |
| `GET` | `/api/source-posts` | List saved posts available as AI context |
| `GET` | `/api/drafts` | List recent drafts |
| `POST` | `/api/drafts/direct` | Create a manual draft |
| `POST` | `/api/drafts/random` | Create a draft from a random saved post |
| `POST` | `/api/drafts/generate` | Generate a Gemini draft |
| `PATCH` | `/api/drafts/<id>` | Edit an unpublished draft |
| `POST` | `/api/drafts/<id>/publish` | Publish an approved draft to Telegram |

## Repository layout

```text
telegram_ai_content_manager/
  services/                 Collection, drafting, Gemini, and Telegram publishing
  static/                   Dashboard assets
  templates/                Dashboard template
  config.py                 Environment and database configuration
  models.py                 SQLAlchemy models
  routes.py                 Web and JSON API routes
tests/                      External-call-free tests
.github/workflows/ci.yml    Test and lint workflow
.env.example                Safe configuration template
render.yaml                 Render Blueprint
wsgi.py                     Production entry point
```

## Security, editorial, and platform notes

- Keep tokens, API keys, and production database URLs out of Git, logs, browser code, and issue trackers. Rotate a credential immediately if it has been exposed.
- The collector uses Telegram's public web preview (`t.me/s/...`). It can only access content Telegram exposes publicly, and its availability can change.
- Monitor only channels you are permitted to use. Respect copyrights, privacy, Telegram's terms, and the terms of any future search/LLM provider.
- Treat source posts and AI output as unverified input. Verify facts, dates, attribution, and rights before publishing.
- Telegram messages have a text limit; this application validates and limits draft text to 4,096 characters.
