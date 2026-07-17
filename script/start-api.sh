#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/reagent-api.log}"
PID_FILE="${PID_FILE:-${LOG_DIR}/reagent-api.pid}"

mkdir -p "${LOG_DIR}"

if [ -f "${PID_FILE}" ]; then
    PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [ -n "${PID}" ] && kill -0 "${PID}" 2>/dev/null; then
        echo "REagent API already running: ${PID}"
        exit 0
    fi
    rm -f "${PID_FILE}"
fi

cd "${ROOT_DIR}"
nohup python main.py serve --host "${API_HOST}" --port "${API_PORT}" >> "${LOG_FILE}" 2>&1 &
echo "$!" > "${PID_FILE}"
echo "REagent API started: $! on ${API_HOST}:${API_PORT}"
