# backend/services/logging_service.py — Per-project timestamped log directories.
#
# Outline:
#   get_project_logger(project_id) -> logging.Logger
#     Lazily create a logger that writes to
#       logs/{YYYY-MM-DD}/{project_id}/pipeline.log
#     with a structured formatter (timestamp, level, stage, message).
#     Multiple calls for the same project_id return the same logger.
#
#   log_error_context(project_id, error, **context)
#     Dump a self-contained error report to
#       logs/{YYYY-MM-DD}/{project_id}/error_{HHMMSS}.log
#     containing the full traceback, passed kwargs, and recent events.
#
#   Log retention policy: the day-directory structure makes manual
#   rotation trivial (`find logs -mtime +14 -delete`).
#
#   Thread safety: Python's stdlib ``logging`` is thread-safe by design.
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from threading import Lock

# Base logs directory. Co-located with the project root so deploy.sh picks
# it up, but also discoverable at /home/{user}/reagent/logs on the server.
_LOGS_ROOT = Path(__file__).resolve().parents[3] / "logs"
_LOGS_ROOT.mkdir(exist_ok=True)

_logger_cache: dict[str, logging.Logger] = {}
_logger_lock = Lock()

# Stdlib-compatible format so `tail -F` stays readable.
_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _today_dir() -> Path:
    d = _LOGS_ROOT / datetime.now().strftime("%Y-%m-%d")
    d.mkdir(exist_ok=True)
    return d


def _project_dir(project_id: str) -> Path:
    d = _today_dir() / project_id
    d.mkdir(exist_ok=True)
    return d


def get_project_logger(project_id: str) -> logging.Logger:
    """Return a cached, per-project logger writing to a dated directory."""
    with _logger_lock:
        cached = _logger_cache.get(project_id)
        if cached is not None:
            return cached

        logger = logging.getLogger(f"reagent.{project_id}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # don't spam the root/uvicorn logger

        log_path = _project_dir(project_id) / "pipeline.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(_FORMATTER)
        logger.addHandler(handler)

        # Also mirror WARNINGs+ to stderr so they show up in the main
        # uvicorn log (which ops people tail).
        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(_FORMATTER)
        logger.addHandler(stderr_handler)

        _logger_cache[project_id] = logger
        return logger


def log_error_context(project_id: str, error: BaseException, **context):
    """Write a self-contained error report for post-mortem debugging.

    File layout:
        logs/{today}/{project_id}/error_{HHMMSS}_{error_type}.log

    Content:
        - timestamp
        - error type + message
        - full traceback
        - caller-supplied context (stage, crew_name, config, etc.)
    """
    ts = datetime.now().strftime("%H%M%S")
    err_type = type(error).__name__
    path = _project_dir(project_id) / f"error_{ts}_{err_type}.log"

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    lines = [
        f"=== Error report ===",
        f"Timestamp:  {datetime.now().isoformat()}",
        f"Project:    {project_id}",
        f"Error type: {err_type}",
        f"Error msg:  {error}",
        f"",
        f"=== Context ===",
    ]
    for k, v in context.items():
        lines.append(f"{k}: {v}")
    lines += [
        f"",
        f"=== Traceback ===",
        tb,
    ]

    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        # If disk is full, don't let logging crash the pipeline.
        pass

    # Also append a one-line summary to the main pipeline log.
    logger = get_project_logger(project_id)
    logger.error(
        "Error captured: %s — %s (full context: %s)",
        err_type, error, path,
    )
