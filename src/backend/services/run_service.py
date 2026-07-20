"""Persistent lifecycle records for individual pipeline executions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from backend.config import settings
from backend.db.mongo import is_duplicate_key_error, pipeline_runs_col


TERMINAL_RUN_STATUSES = {"completed", "failed", "error", "cancelled", "rejected"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunQuotaExceeded(RuntimeError):
    pass


class RunService:
    async def create(self, project: dict, config: dict) -> dict:
        now = _now()
        run_id = uuid.uuid4().hex[:12]
        doc = {
            "run_id": run_id,
            "project_id": project["project_id"],
            "user_id": project["user_id"],
            "status": "queued",
            "current_stage": None,
            "current_crew": None,
            "last_error": None,
            "config_snapshot": {
                "project_name": config.get("project_name"),
                "description": config.get("description"),
                "srs_template": config.get("srs_template"),
                "srs_example_path": config.get("srs_example_path"),
            },
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
        }
        # A sparse unique (user_id, active_slot) index makes quota allocation
        # atomic even when several browser tabs start pipelines simultaneously.
        inserted = False
        for slot in range(settings.PIPELINE_MAX_ACTIVE_PER_USER):
            doc["active_slot"] = slot
            try:
                await pipeline_runs_col().insert_one(doc)
                inserted = True
                break
            except Exception as error:
                if is_duplicate_key_error(error):
                    continue
                raise
        if not inserted:
            raise RunQuotaExceeded(
                "User pipeline concurrency limit reached "
                f"({settings.PIPELINE_MAX_ACTIVE_PER_USER})"
            )
        return {key: value for key, value in doc.items() if key != "_id"}

    async def update_status(self, run_id: str, **fields) -> None:
        if not run_id:
            return
        now = _now()
        fields["updated_at"] = now
        status = fields.get("status")
        if status == "running":
            # Set started_at once without overwriting the original start time.
            await pipeline_runs_col().update_one(
                {"run_id": run_id, "started_at": None},
                {"$set": {"started_at": now}},
            )
        if status in TERMINAL_RUN_STATUSES:
            fields["finished_at"] = now
        update: dict = {"$set": fields}
        if status in TERMINAL_RUN_STATUSES:
            update["$unset"] = {"active_slot": ""}
        await pipeline_runs_col().update_one({"run_id": run_id}, update)

    async def list_by_project(self, project_id: str, limit: int = 50) -> dict:
        cursor = pipeline_runs_col().find(
            {"project_id": project_id},
            {"_id": 0, "config_snapshot.description": 0},
        ).sort("created_at", -1)
        runs = await cursor.to_list(length=max(1, min(limit, 100)))
        return {"project_id": project_id, "runs": runs}

    async def get(self, project_id: str, run_id: str) -> dict | None:
        return await pipeline_runs_col().find_one(
            {"project_id": project_id, "run_id": run_id}, {"_id": 0}
        )
