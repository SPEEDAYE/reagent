"""Structured logging helpers for REagent runs.

Logs support level, run id, seed/config identifiers, and structured context.
Secret-looking keys are redacted before they are emitted.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any


SECRET_MARKERS = ("key", "token", "secret", "password", "credential")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if any(marker in key.lower() for marker in SECRET_MARKERS) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def get_logger(name: str = "reagent", run_id: str | None = None) -> logging.Logger:
    logger_name = f"{name}.{run_id}" if run_id else name
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_root = _project_root() / "logs"
    log_root.mkdir(exist_ok=True)
    log_path = log_root / f"{run_id or 'reagent'}.log"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def log_event(
    level: str,
    message: str,
    *,
    run_id: str | None = None,
    seed: str | int | None = None,
    config_id: str | None = None,
    **context: Any,
) -> None:
    payload = {
        "run_id": run_id or os.getenv("REAGENT_RUN_ID"),
        "seed": seed or os.getenv("REAGENT_SEED"),
        "config_id": config_id or os.getenv("REAGENT_CONFIG_ID"),
        "context": _redact(context),
    }
    logger = get_logger(run_id=payload["run_id"])
    logger.log(getattr(logging, level.upper(), logging.INFO), "%s %s", message, json.dumps(payload, ensure_ascii=False))
