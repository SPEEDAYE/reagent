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
import re
from datetime import datetime, timezone
from backend.db.mongo import (
    projects_col,
    artifacts_col,
    artifact_versions_col,
    files_col,
    pipeline_runs_col,
)
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
            "archived": False,
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

    async def list_by_user(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        statuses: list[str] | None = None,
        archived: bool | None = False,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> dict:
        query: dict = {"user_id": user_id}
        if archived is not None:
            query["archived"] = True if archived else {"$ne": True}
        if search:
            query["$or"] = [
                {"project_name": {"$regex": re.escape(search), "$options": "i"}},
                {"description": {"$regex": re.escape(search), "$options": "i"}},
            ]
        if statuses:
            query["status"] = {"$in": statuses}

        allowed_sorts = {"updated_at", "created_at", "project_name", "status"}
        sort_field = sort_by if sort_by in allowed_sorts else "updated_at"
        direction = -1 if sort_order.lower() != "asc" else 1
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        total = await projects_col().count_documents(query)
        cursor = (
            projects_col()
            .find(query, {"_id": 0, "description": 0})
            .sort(sort_field, direction)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        projects = await cursor.to_list(length=page_size)
        return {
            "projects": projects,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }

    async def active_for_user(self, user_id: str) -> dict:
        """Return the single project a returning user should resume.

        The frontend keeps ``project_id`` only in browser localStorage, which
        can be lost (private window, different origin, cleared storage, a
        project started without going through create). This endpoint lets the
        client rediscover its work from the server instead — the backend is the
        source of truth for "what is running".

        Selection priority:
          1. A project actively needing attention (queued/running/interrupted)
          2. Otherwise the most-recently updated project

        Returns ``{"active": <project doc>}`` or ``{"active": None}`` when the
        user has no projects.
        """
        cursor = projects_col().find(
            {"user_id": user_id},
            {"_id": 0, "description": 0},
        ).sort("updated_at", -1)
        projects = await cursor.to_list(length=100)
        if not projects:
            return {"active": None}
        for status in ("running", "interrupted", "queued"):
            for p in projects:
                if p.get("status") == status:
                    return {"active": p}
        return {"active": projects[0]}

    async def get(self, project_id: str) -> dict | None:
        doc = await projects_col().find_one(
            {"project_id": project_id}, {"_id": 0}
        )
        return doc or {"error": "Project not found"}

    async def update(self, project_id: str, fields: dict) -> dict:
        allowed = {"project_name", "description", "archived"}
        update = {
            key: value
            for key, value in fields.items()
            if key in allowed and value is not None
        }
        if not update:
            return await self.get(project_id)
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await projects_col().update_one(
            {"project_id": project_id}, {"$set": update}
        )
        return await self.get(project_id)

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
        versions = await artifact_versions_col().delete_many({"project_id": project_id})
        r3 = await files_col().delete_many({"project_id": project_id})
        r4 = await pipeline_runs_col().delete_many({"project_id": project_id})
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
            "deleted_artifact_versions": versions.deleted_count,
            "deleted_files": r3.deleted_count,
            "deleted_runs": r4.deleted_count,
        }

    async def update_status(self, project_id: str, **fields):
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        await projects_col().update_one(
            {"project_id": project_id},
            {"$set": fields},
        )
