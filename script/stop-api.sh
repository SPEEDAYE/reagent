#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs}"
PID_FILE="${PID_FILE:-${LOG_DIR}/reagent-api.pid}"

if [ ! -f "${PID_FILE}" ]; then
    echo "REagent API is not running"
    exit 0
fi

PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
if [ -n "${PID}" ] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" || true
    echo "Stopped REagent API: ${PID}"
fi
rm -f "${PID_FILE}"
