# backend/models/requests.py — Pydantic request schemas.
#
# Outline:
#   ProjectCreateRequest  user_id, project_name, description,
#                         srs_template (IEEE|Initial|None), srs_example_path
#   StreamCreateRequest   project_id, user_id, human_request?, data_files?
#   StreamResumeRequest   project_id, resume_type
#                         (feedback|accept|redo_artifact|skip), human_comment?,
#                         target_artifact?, prune_downstream?
#   ExportPdfRequest      project_id, artifact_name
from pydantic import BaseModel
from typing import Optional, Literal


class ProjectCreateRequest(BaseModel):
    user_id: str
    project_name: str
    description: str
    srs_template: Optional[Literal["IEEE", "Initial"]] = None
    srs_example_path: Optional[str] = None


class StreamCreateRequest(BaseModel):
    project_id: str
    user_id: str
    human_request: Optional[str] = None
    data_files: Optional[list[str]] = None
    start_from: Optional[str] = None


class StreamResumeRequest(BaseModel):
    project_id: str
    resume_type: Literal["feedback", "accept", "redo_artifact", "skip"]
    human_comment: Optional[str] = None
    target_artifact: Optional[str] = None
    prune_downstream: Optional[bool] = False


class ExportPdfRequest(BaseModel):
    project_id: str
    artifact_name: str
