# backend/api/routes/files.py — File upload endpoints.
#
# Outline:
#   POST /files/upload      multipart upload. file_type="data" stores as
#                           dataset/uploads/{pid}/{filename}; file_type="template"
#                           supports actions: (default) upload_template,
#                           action="confirm" → confirm_template,
#                           action="revise" + feedback → revise_template.
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form

from backend.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])
svc = FileService()


@router.post("/upload")
async def upload_file(
    project_id: str = Form(...),
    file_type: str = Form(...),
    action: Optional[str] = Form(None),
    feedback: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Unified file upload endpoint.

    - file_type="data" + file  -> upload project data file
    - file_type="template" + file -> upload SRS template (returns preview)
    - file_type="template" + action="confirm" -> confirm template
    - file_type="template" + action="revise" + feedback -> revise template
    """
    if file_type == "template":
        if action == "confirm":
            return await svc.confirm_template(project_id)
        elif action == "revise":
            return await svc.revise_template(project_id, feedback)
        elif file:
            return await svc.upload_template(project_id, file)
        else:
            return {"error": "Template upload requires a file or an action"}
    else:
        if not file:
            return {"error": "Data upload requires a file"}
        return await svc.upload_data(project_id, file)
