"""Persistence and replay for low-frequency pipeline lifecycle events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.db.mongo import pipeline_events_col


class EventService:
    async def persist(self, event: dict) -> None:
        run_id = event.get("run_id")
        event_id = event.get("_seq")
        if not run_id or event_id is None or event.get("type") == "token":
            return
        now = datetime.now(timezone.utc)
        doc = {
            "run_id": run_id,
            "project_id": event.get("project_id"),
            "event_id": int(event_id),
            "type": event.get("type", "message"),
            "payload": dict(event),
            "created_at": now,
            "expires_at": now + timedelta(days=settings.EVENT_RETENTION_DAYS),
        }
        await pipeline_events_col().update_one(
            {"run_id": run_id, "event_id": int(event_id)},
            {"$setOnInsert": doc},
            upsert=True,
        )

    async def list_after(
        self, run_id: str, after_event_id: int = 0, limit: int = 1000
    ) -> list[dict]:
        cursor = pipeline_events_col().find(
            {"run_id": run_id, "event_id": {"$gt": after_event_id}},
            {"_id": 0, "payload": 1},
        ).sort("event_id", 1).limit(max(1, min(limit, 5000)))
        docs = await cursor.to_list(length=max(1, min(limit, 5000)))
        return [doc["payload"] for doc in docs if doc.get("payload")]
