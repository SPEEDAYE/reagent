# backend/services/project_service.py — Project CRUD against MongoDB.
#
# Outline:
#   ProjectService
#     create(data)            insert new project (UUID[:8] id) → return stub
#     list_by_user(user_id)   latest-first listing (omits description)
#     get(project_id)         single project doc or {error}
#     delete(project_id)      cascade-delete projects/artifacts/files
#                             collections + upload_dir + output_dir
#     update_status(pid, **)  partial update (auto-bumps updated_at)
import uuid
import shutil
import os
from datetime import datetime, timezone
from backend.db.mongo import projects_col, artifacts_col, files_col
from backend.config import settings


class ProjectService:
    async def create(self, data: dict) -> dict:
        project_id = uuid.uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "project_id": project_id,
            "user_id": data["user_id"],
            "project_name": data["project_name"],
            "description": data["description"],
            "srs_template": data.get("srs_template"),
            "srs_example_path": data.get("srs_example_path") or "src/util/doc_template/document_example.md",
            "status": "created",
            "current_stage": None,
            "current_crew": None,
            "created_at": now,
            "updated_at": now,
        }
        await projects_col().insert_one(doc)
        return {
            "project_id": project_id,
            "status": "created",
            "created_at": now,
        }

    async def list_by_user(self, user_id: str) -> dict:
        cursor = projects_col().find(
            {"user_id": user_id},
            {"_id": 0, "description": 0},
        ).sort("updated_at", -1)
        projects = await cursor.to_list(length=100)
        return {"projects": projects}

    async def get(self, project_id: str) -> dict | None:
        doc = await projects_col().find_one(
            {"project_id": project_id}, {"_id": 0}
        )
        return doc or {"error": "Project not found"}

    async def delete(self, project_id: str) -> dict:
        # Cancel any running pipeline for this project before deleting data.
        # This unblocks the worker thread (if blocked in multiline_input)
        # and marks the pipeline for cancellation so it exits cleanly.
        from backend.services.execution import ExecutionService
        exec_svc = ExecutionService()
        try:
            await exec_svc.cancel(project_id)
        except Exception:
            pass  # Best-effort: don't let cancel failure block deletion

        r1 = await projects_col().delete_many({"project_id": project_id})
        r2 = await artifacts_col().delete_many({"project_id": project_id})
        r3 = await files_col().delete_many({"project_id": project_id})
        # Clean upload directory
        upload_dir = os.path.join(settings.UPLOAD_DIR, project_id)
        if os.path.isdir(upload_dir):
            shutil.rmtree(upload_dir, ignore_errors=True)
        # Clean per-project output directory
        output_dir = os.path.join(settings.OUTPUT_DIR, project_id)
        if os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        return {
            "status": "deleted",
            "project_id": project_id,
            "deleted_projects": r1.deleted_count,
            "deleted_artifacts": r2.deleted_count,
            "deleted_files": r3.deleted_count,
        }

    async def update_status(self, project_id: str, **fields):
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        await projects_col().update_one(
            {"project_id": project_id},
            {"$set": fields},
        )
