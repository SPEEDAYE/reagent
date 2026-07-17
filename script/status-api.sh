#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs}"
PID_FILE="${PID_FILE:-${LOG_DIR}/reagent-api.pid}"

if [ -f "${PID_FILE}" ]; then
    PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [ -n "${PID}" ] && kill -0 "${PID}" 2>/dev/null; then
        echo "REagent API RUNNING: pid=${PID} port=${API_PORT}"
        if command -v curl >/dev/null 2>&1; then
            echo -n "Health: "
            curl -fsS "http://127.0.0.1:${API_PORT}/health" || echo "unreachable"
        fi
        exit 0
    fi
fi
echo "REagent API STOPPED"
