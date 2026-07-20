# backend/config.py — Settings singleton.
#
# Outline:
#   Loads .env from repo root (falls back to parent dir).
#   Settings class:
#     DATABASE_TYPE   sqlite (default) or mongodb
#     SQLITE_PATH     embedded local database path
#     MONGODB_URI     optional production MongoDB URI
#     DB_NAME         default "reagent"
#     CORS_ORIGINS    default ["*"] (dev only)
#     PROJECT_ROOT    absolute path to repository project root
#     OUTPUT_DIR      PROJECT_ROOT/experiment
#     UPLOAD_DIR      PROJECT_ROOT/dataset/uploads
#   settings          module-level singleton consumed by main.py and services.
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env from project root
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Fallback: try parent directory
    _fallback = PROJECT_ROOT.parent / ".env"
    if _fallback.exists():
        load_dotenv(_fallback)


class Settings:
    # SQLite is the zero-setup default. Set DATABASE_TYPE=mongodb for the
    # existing production deployment.
    DATABASE_TYPE: str = os.getenv("DATABASE_TYPE", "sqlite").strip().lower()
    SQLITE_PATH: str = os.getenv(
        "SQLITE_PATH", str(PROJECT_ROOT / "data" / "reagent.db")
    )
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "reagent")
    CORS_ORIGINS: list[str] = ["*"]
    PROJECT_ROOT: str = str(PROJECT_ROOT)
    OUTPUT_DIR: str = os.path.join(PROJECT_ROOT, "experiment")
    UPLOAD_DIR: str = os.path.join(PROJECT_ROOT, "dataset", "uploads")
    # Authentication migration switches.
    #
    # AUTH_REQUIRED=0 keeps the current intranet deployment working while the
    # API gateway is being updated.  Set it to 1 in production once either a
    # shared token secret or trusted proxy identity headers are configured.
    AUTH_REQUIRED: bool = os.getenv("AUTH_REQUIRED", "0").lower() in {
        "1", "true", "yes", "on",
    }
    AUTH_TOKEN_SECRET: str = os.getenv("AUTH_TOKEN_SECRET", "")
    AUTH_TOKEN_ALGORITHM: str = os.getenv("AUTH_TOKEN_ALGORITHM", "HS256")
    AUTH_TRUST_PROXY_HEADERS: bool = os.getenv(
        "AUTH_TRUST_PROXY_HEADERS", "0"
    ).lower() in {"1", "true", "yes", "on"}
    AUTH_PROXY_SHARED_SECRET: str = os.getenv("AUTH_PROXY_SHARED_SECRET", "")
    AUTH_PROXY_SECRET_HEADER: str = os.getenv(
        "AUTH_PROXY_SECRET_HEADER", "X-Proxy-Secret"
    )
    AUTH_USER_HEADER: str = os.getenv("AUTH_USER_HEADER", "X-User-Code")
    AUTH_USERNAME_HEADER: str = os.getenv("AUTH_USERNAME_HEADER", "X-Username")
    AUTH_ROLES_HEADER: str = os.getenv("AUTH_ROLES_HEADER", "X-User-Roles")
    EVENT_RETENTION_DAYS: int = int(os.getenv("EVENT_RETENTION_DAYS", "7"))
    PIPELINE_MAX_WORKERS: int = max(1, int(os.getenv("PIPELINE_MAX_WORKERS", "2")))
    PIPELINE_MAX_ACTIVE_PER_USER: int = max(
        1, int(os.getenv("PIPELINE_MAX_ACTIVE_PER_USER", "2"))
    )


settings = Settings()
