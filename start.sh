#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "[1/3] Creating Python virtual environment..."
  python3 -m venv .venv
  echo "[2/3] Installing dependencies. The first run can take several minutes..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

[ -f .env ] || cp .env.example .env
API_PORT="${API_PORT:-8000}"
echo "[3/3] Starting REagent with embedded SQLite..."
echo "API: http://127.0.0.1:${API_PORT}"
echo "Docs: http://127.0.0.1:${API_PORT}/docs"
exec .venv/bin/python main.py serve --host 127.0.0.1 --port "$API_PORT"
