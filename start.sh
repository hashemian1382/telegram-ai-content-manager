#!/usr/bin/env bash
#
# Telegram AI Content Manager - one-command setup & run.
#
# Usage:
#   ./start.sh           install dependencies (first run) and start the app
#   ./start.sh install   create .venv, install dependencies, prepare .env
#   ./start.sh run       start the dev server (auto-installs first)
#   ./start.sh test      run the test suite
#   ./start.sh lint      run the Ruff linter
#
# Works on Linux, macOS, Codespaces, and Windows (Git Bash / WSL).
# Set PYTHON to pick an interpreter, e.g.: PYTHON=python3.12 ./start.sh

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV_DIR=".venv"

# Resolve the interpreter inside the venv (Unix vs Windows Git Bash).
if [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then
  VENV_PY="$VENV_DIR/Scripts/python.exe"
else
  VENV_PY="$VENV_DIR/bin/python"
fi

install() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo ">> Creating virtual environment (.venv)"
    "$PYTHON" -m venv "$VENV_DIR"
  fi
  echo ">> Installing dependencies"
  "$VENV_PY" -m pip install --quiet --upgrade pip
  "$VENV_PY" -m pip install --quiet -e ".[dev]"
  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ">> Created .env from .env.example (add your tokens there)"
  fi
  echo ">> Done"
}

ensure_installed() {
  if [[ ! -x "$VENV_PY" ]]; then
    install
  fi
}

case "${1:-run}" in
  install)
    install
    ;;
  run)
    ensure_installed
    echo ">> Server running at http://localhost:5000"
    exec "$VENV_PY" app.py
    ;;
  test)
    ensure_installed
    "$VENV_PY" -m pytest -q
    ;;
  lint)
    ensure_installed
    "$VENV_PY" -m ruff check .
    ;;
  help | -h | --help)
    sed -n '3,14p' "$0"
    ;;
  *)
    echo "Unknown command: $1 (try: install | run | test | lint | help)" >&2
    exit 1
    ;;
esac
