# Telegram AI Content Manager

A self-hostable workspace for collecting ideas from **public Telegram channels**, creating Persian-language content drafts, reviewing them, and publishing approved drafts to a Telegram channel through a bot.

Built and maintained by **Ali Hashemian**.

> This repository is intentionally designed around editorial control: AI output is saved as a draft first, and a person must explicitly approve publication.

---

## 🚀 شروع سریع (Quick start)

فقط کافی است این سه دستور را اجرا کنید — اسکریپت `start.sh` در اولین اجرا خودش محیط مجازی را می‌سازد، وابستگی‌ها را نصب می‌کند، فایل `.env` را آماده می‌کند و برنامه را اجرا می‌کند:

```bash
git clone https://github.com/hashemian1382/telegram-ai-content-manager.git
cd telegram-ai-content-manager
./start.sh
```

سپس در مرورگر باز کنید: **http://localhost:5000**

> ⚙️ فقط برای استفاده از امکانات Telegram و Gemini، مقدارهای `TELEGRAM_BOT_TOKEN`، `TELEGRAM_CHANNEL_ID` و `GEMINI_API_KEY` را در فایل `.env` وارد کنید.

## The `start.sh` script

| Command | What it does |
| --- | --- |
| `./start.sh` | Install (first run only) and start the dev server |
| `./start.sh install` | Create `.venv`, install app + dev dependencies, create `.env` |
| `./start.sh run` | Start the dev server (auto-installs first) |
| `./start.sh test` | Run the test suite |
| `./start.sh lint` | Run the Ruff linter |

Works on Linux, macOS, GitHub Codespaces, and Windows (Git Bash / WSL). Optional: `PYTHON=python3.12 ./start.sh` to force a specific interpreter.

## Manual setup (without the script)

```bash
git clone https://github.com/hashemian1382/telegram-ai-content-manager.git
cd telegram-ai-content-manager
python -m venv .venv
source .venv/bin/activate        # Windows (Git Bash): source .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env             # then edit .env
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

## GitHub Codespaces (zero-setup cloud environment)

1. Open the repository on GitHub and click **Code → Codespaces → Create codespace on master** — or open <https://codespaces.new/hashemian1382/telegram-ai-content-manager> directly.
2. The dev container (`/.devcontainer`) automatically runs `./start.sh install`, so dependencies are ready when the workspace loads.
3. Start the app with `./start.sh run` and open the forwarded **port 5000** (VS Code prompts you automatically).

## Environment variables

Copy `.env.example` to `.env` and fill in what you need. **Never commit `.env`.** All values are optional; the app runs with none of them (minus AI/Telegram features).

| Variable | Required for | Description | Default |
| --- | --- | --- | --- |
| `SECRET_KEY` | Production | Random secret for session signing. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` | `change-me-in-production` |
| `DATABASE_URL` | Production | SQLAlchemy URL. SQLite locally (file lives in `instance/`, gitignored), PostgreSQL on Render/Neon. `postgres://`/`postgresql://` URLs are normalized automatically for Psycopg 3 | `sqlite:///telegram_ai_content_manager.db` |
| `TELEGRAM_BOT_TOKEN` | Publishing | Bot token from [@BotFather](https://t.me/BotFather) | — |
| `TELEGRAM_CHANNEL_ID` | Publishing | Target channel `@username` or numeric chat id (bot must be an admin) | — |
| `GEMINI_API_KEY` | AI drafting | API key from <https://aistudio.google.com/apikey> | — |
| `GEMINI_MODELS` | AI drafting | Comma-separated model list offered in the UI | `gemini-2.5-flash,gemini-2.5-flash-lite` |
| `SCRAPER_LIMIT` | — | Latest public posts fetched per channel per run | `10` |
| `SCRAPER_TIMEOUT` | — | Per-channel scrape timeout in seconds | `20` |

### Get a Telegram bot token in one minute

1. Message [@BotFather](https://t.me/BotFather) and run `/newbot`.
2. Copy the API token into `TELEGRAM_BOT_TOKEN`.
3. Add the bot as **administrator** of your target channel and put the channel `@username` (or numeric id) into `TELEGRAM_CHANNEL_ID`.

## What is included

- Register public Telegram source channels and collect their currently accessible posts into a SQL database
- Store source text, post links, timestamps, media flags, and collection-run results
- Write a draft directly, create one from a random saved source post, or generate a Persian draft with Gemini
- Select saved source posts as context for Gemini, then edit every draft before publication
- Publish an approved text draft with the Telegram Bot API
- RTL Persian dashboard, JSON API, health check, tests, GitHub Actions CI, and a Render blueprint
- SQLite for local development and PostgreSQL for hosted environments

## Requirements

- Python 3.11+
- A Telegram bot token and a target channel where that bot is an administrator (only for publishing)
- A Gemini API key (only for AI generation)
- PostgreSQL for production deployments; SQLite is used by default locally

## Development commands

```bash
./start.sh test        # or: pytest -q
./start.sh lint        # or: ruff check .
./start.sh run         # dev server on http://localhost:5000
gunicorn app:app --bind 0.0.0.0:8000 --workers 2 --timeout 120   # production-style local run
```

## Deploy on Render

The included `render.yaml` creates a Web Service and a PostgreSQL database.

1. Push this repository to GitHub.
2. In Render, select **New → Blueprint** and choose the repository.
3. Add these secret environment variables to the Web Service: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, and `GEMINI_API_KEY`.
4. Deploy. Render supplies `DATABASE_URL`; the blueprint generates `SECRET_KEY`.

The same production command is available in `Procfile`:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
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
app.py                      Single entry point (dev: python app.py · prod: gunicorn app:app)
start.sh                    One-command setup & run script
pyproject.toml              Dependencies and tool configuration
.env.example                Safe configuration template
Procfile / render.yaml      Deployment (Heroku-style / Render Blueprint)
telegram_ai_content_manager/
  __init__.py               Application factory
  config.py                 .env loading and database URL helpers
  models.py                 Database setup and SQLAlchemy models
  routes.py                 Web dashboard and JSON API routes
  services.py               Scraping, Gemini drafting, Telegram publishing
  static/                   Dashboard assets
  templates/                Dashboard template
tests/                      External-call-free tests
.github/workflows/ci.yml    Test and lint workflow
.devcontainer/              GitHub Codespaces configuration
```

## Security, editorial, and platform notes

- Keep tokens, API keys, and production database URLs out of Git, logs, browser code, and issue trackers. Rotate a credential immediately if it has been exposed.
- The collector uses Telegram's public web preview (`t.me/s/...`). It can only access content Telegram exposes publicly, and its availability can change.
- Monitor only channels you are permitted to use. Respect copyrights, privacy, Telegram's terms, and the terms of any future search/LLM provider.
- Treat source posts and AI output as unverified input. Verify facts, dates, attribution, and rights before publishing.
- Telegram messages have a text limit; this application validates and limits draft text to 4,096 characters.
