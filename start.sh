#!/usr/bin/env bash
#
# Telegram AI Content Manager — one-command setup & run script.
#
# Works on Linux, macOS, GitHub Codespaces and other cloud dev environments,
# plus Windows via Git Bash / WSL.
#
# Usage:
#   ./start.sh            install (if needed) and start the dev server
#   ./start.sh install    create venv, install dependencies, prepare .env
#   ./start.sh run        start the dev server (auto-installs first)
#   ./start.sh test       run the test suite
#   ./start.sh lint       run the Ruff linter
#   ./start.sh help       show this help
#
# Optional environment variable:
#   PYTHON_BIN   Python interpreter to use (default: python3)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/.venv"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Pick the correct venv interpreter (Windows Git Bash vs Unix).
if [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then
  VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
else
  VENV_PYTHON="$VENV_DIR/bin/python"
fi

# ---------- pretty output ----------
if [[ -t 1 ]]; then
  GREEN=$'\033[32m'; CYAN=$'\033[36m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  GREEN=""; CYAN=""; YELLOW=""; RED=""; RESET=""
fi
info() { printf '%s%s%s\n' "$CYAN" "$*" "$RESET"; }
ok()   { printf '%s✔ %s%s\n' "$GREEN" "$*" "$RESET"; }
warn() { printf '%s! %s%s\n' "$YELLOW" "$*" "$RESET"; }
die()  { printf '%s✖ %s%s\n' "$RED" "$*" "$RESET" >&2; exit 1; }

usage() {
  cat <<'EOF'
Telegram AI Content Manager — one-command setup & run script

Usage:
  ./start.sh            install (if needed) and start the dev server
  ./start.sh install    create venv, install dependencies, prepare .env
  ./start.sh run        start the dev server (auto-installs first)
  ./start.sh test       run the test suite
  ./start.sh lint       run the Ruff linter
  ./start.sh help       show this help

Works on Linux, macOS, GitHub Codespaces, and Windows (Git Bash / WSL).
Set PYTHON_BIN to choose a Python interpreter (default: python3).
EOF
}

check_python() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    die "Python not found ('$PYTHON_BIN'). Install Python 3.11+ first: https://www.python.org/downloads/"
  fi
  if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    local v
    v="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    die "Python $v found, but Python 3.11+ is required. Install a newer version: https://www.python.org/downloads/"
  fi
  info "Using $("$PYTHON_BIN" -c 'import sys; print("Python " + sys.version.split()[0])')"
}

create_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    ok ".env already exists"
    return
  fi
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    warn ".env created from .env.example — edit it to add your TELEGRAM_BOT_TOKEN / GEMINI_API_KEY"
  else
    warn ".env.example not found — skipping .env creation"
  fi
}

cmd_install() {
  check_python
  if [[ -d "$VENV_DIR" ]]; then
    ok "Virtual environment already exists (.venv)"
  else
    info "Creating virtual environment (.venv)…"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    ok "Virtual environment created"
  fi
  info "Upgrading pip…"
  "$VENV_PYTHON" -m pip install --upgrade pip
  info "Installing dependencies (app + dev tools)…"
  "$VENV_PYTHON" -m pip install -e ".[dev]"
  ok "Dependencies installed"
  create_env_file
  ok "Setup complete — run './start.sh run' to start the app"
}

ensure_ready() {
  if [[ ! -d "$VENV_DIR" || ! -x "$VENV_PYTHON" ]]; then
    warn "First run detected — installing dependencies…"
    cmd_install
  fi
  create_env_file
}

cmd_run() {
  ensure_ready
  info "Starting dev server → http://localhost:5000"
  exec "$VENV_PYTHON" run.py
}

cmd_test() {
  ensure_ready
  info "Running tests…"
  "$VENV_PYTHON" -m pytest -q
}

cmd_lint() {
  ensure_ready
  info "Running Ruff linter…"
  "$VENV_PYTHON" -m ruff check .
}

ACTION="${1:-run}"
case "$ACTION" in
  install)            cmd_install ;;
  run)                cmd_run ;;
  test)               cmd_test ;;
  lint)               cmd_lint ;;
  help|-h|--help)     usage ;;
  *)                  warn "Unknown command: $ACTION"; echo; usage; exit 1 ;;
esac
