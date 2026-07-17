#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
"${ROOT_DIR}/script/stop-api.sh"
sleep 1
"${ROOT_DIR}/script/start-api.sh"
