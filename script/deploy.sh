#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_NAME="$(basename "${ROOT_DIR}")"
PROJECT_PARENT="$(dirname "${ROOT_DIR}")"
TARBALL_NAME="${TARBALL_NAME:-${PROJECT_NAME}.tar.gz}"
LOCAL_TARBALL="${LOCAL_TARBALL:-/tmp/${TARBALL_NAME}}"

usage() {
    cat <<EOF
Usage: script/deploy.sh [pack]

Environment:
  LOCAL_TARBALL  Local package path (default: ${LOCAL_TARBALL})
  TARBALL_NAME   Package filename   (default: ${TARBALL_NAME})
EOF
}

pack() {
    tar czf "${LOCAL_TARBALL}" \
        --exclude="${PROJECT_NAME}/.git" \
        --exclude="${PROJECT_NAME}/.venv" \
        --exclude="${PROJECT_NAME}/venv" \
        --exclude="${PROJECT_NAME}/__pycache__" \
        --exclude="${PROJECT_NAME}/.pytest_cache" \
        --exclude="${PROJECT_NAME}/.DS_Store" \
        --exclude="${PROJECT_NAME}/logs" \
        --exclude="${PROJECT_NAME}/output" \
        --exclude="${PROJECT_NAME}/uploads" \
        --exclude="${PROJECT_NAME}/crewai_storage" \
        --exclude="${PROJECT_NAME}/dataset/template-cache" \
        --exclude="${PROJECT_NAME}/dataset/uploads" \
        --exclude="${PROJECT_NAME}/experiment/*/*.log" \
        --exclude="${PROJECT_NAME}/experiment/*/*.pkl" \
        --exclude="${PROJECT_NAME}/**/__pycache__" \
        --exclude="${PROJECT_NAME}/**/*.pyc" \
        -C "${PROJECT_PARENT}" \
        "${PROJECT_NAME}"
    echo "Created package: ${LOCAL_TARBALL}"
}

case "${1:-pack}" in
    pack)
        pack
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
