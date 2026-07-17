# backend/models/responses.py — Pydantic response schemas (currently thin;
# most endpoints return dicts directly).
#   ProjectResponse   project_id, status, created_at
#   StatusResponse    status, project_id
from pydantic import BaseModel
from typing import Optional


class ProjectResponse(BaseModel):
    project_id: str
    status: str
    created_at: Optional[str] = None


class StatusResponse(BaseModel):
    status: str
    project_id: Optional[str] = None
