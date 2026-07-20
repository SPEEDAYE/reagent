# backend/api/routes/health.py — Health check.
# GET /health pings the configured database and returns status metadata.
from datetime import datetime, timezone
from fastapi import APIRouter
from backend.db.mongo import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    db = get_db()
    db_ok = False
    if db is not None:
        try:
            await db.command("ping")
            db_ok = True
        except Exception:
            pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "db_connected": db_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
