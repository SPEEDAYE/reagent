# backend/services/file_service.py — Multipart upload handler.
#
# Outline:
#   FileService
#     upload_data(pid, file)     save to dataset/uploads/{pid}/, insert files_col
#                                (file_type="data" for PDFs/docs)
#     upload_template(pid, file) save custom SRS template (file_type="template")
#                                returns status="preview" pending confirm
#     confirm_template(pid)      stub: marks template confirmed
#     revise_template(pid, fb)   stub: accepts revision feedback
import os
import uuid
from datetime import datetime, timezone
from fastapi import UploadFile
from backend.config import settings
from backend.db.mongo import files_col


class FileService:
    async def upload_data(self, project_id: str, file: UploadFile) -> dict:
        """Upload a data file (PDF, DOCX, image, etc.)."""
        file_id = uuid.uuid4().hex[:8]
        upload_dir = os.path.join(settings.UPLOAD_DIR, project_id)
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)

        content_bytes = await file.read()
        with open(filepath, "wb") as f:
            f.write(content_bytes)

        doc = {
            "file_id": file_id,
            "project_id": project_id,
            "filename": file.filename,
            "file_type": "data",
            "file_path": filepath,
            "size_bytes": len(content_bytes),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        await files_col().insert_one(doc)
        return {
            "file_id": file_id,
            "filename": file.filename,
            "file_type": "data",
            "size_bytes": len(content_bytes),
            "parsed": False,
            "extracted_content_preview": "",
        }

    async def upload_template(self, project_id: str, file: UploadFile) -> dict:
        """Upload an SRS template and return preview of its structure."""
        file_id = uuid.uuid4().hex[:8]
        upload_dir = os.path.join(settings.UPLOAD_DIR, project_id)
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)

        content_bytes = await file.read()
        with open(filepath, "wb") as f:
            f.write(content_bytes)

        doc = {
            "file_id": file_id,
            "project_id": project_id,
            "filename": file.filename,
            "file_type": "template",
            "file_path": filepath,
            "size_bytes": len(content_bytes),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        await files_col().insert_one(doc)

        return {
            "status": "preview",
            "file_id": file_id,
            "template_name": file.filename,
            "source_format": os.path.splitext(file.filename)[1].lstrip("."),
            "message": "Template uploaded. Use action=confirm to apply.",
        }

    async def confirm_template(self, project_id: str) -> dict:
        return {"status": "confirmed", "project_id": project_id}

    async def revise_template(self, project_id: str, feedback: str | None) -> dict:
        return {
            "status": "revision_requested",
            "project_id": project_id,
            "feedback": feedback,
        }
