# backend/config.py — Settings singleton.
#
# Outline:
#   Loads .env from repo root (falls back to parent dir).
#   Settings class:
#     MONGODB_URI     default mongodb://localhost:27017
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
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "reagent")
    CORS_ORIGINS: list[str] = ["*"]
    PROJECT_ROOT: str = str(PROJECT_ROOT)
    OUTPUT_DIR: str = os.path.join(PROJECT_ROOT, "experiment")
    UPLOAD_DIR: str = os.path.join(PROJECT_ROOT, "dataset", "uploads")


settings = Settings()
