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
from pydantic import BaseModel, Field
from typing import Optional, Literal


class ProjectCreateRequest(BaseModel):
    # Deprecated compatibility field. In strict auth mode the backend derives
    # this value from the authenticated identity.
    user_id: Optional[str] = None
    project_name: str
    description: str
    srs_template: Optional[Literal["IEEE", "Initial"]] = None
    srs_example_path: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    archived: Optional[bool] = None


class StreamCreateRequest(BaseModel):
    project_id: str
    user_id: Optional[str] = None
    human_request: Optional[str] = None
    data_files: Optional[list[str]] = None
    start_from: Optional[str] = None


class StreamResumeRequest(BaseModel):
    project_id: str
    resume_type: Literal["feedback", "accept", "redo_artifact", "skip"]
    human_comment: Optional[str] = None
    target_artifact: Optional[str] = None
    target_artifacts: Optional[list[str]] = None
    prune_downstream: Optional[bool] = False


class StreamCancelRequest(BaseModel):
    project_id: str


class ExportPdfRequest(BaseModel):
    project_id: str
    artifact_name: str
    run_id: Optional[str] = None


class ArtifactVersionCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5_000_000)
    base_version: Optional[int] = Field(default=None, ge=1)
    based_on_version: Optional[int] = Field(default=None, ge=1)
    change_summary: Optional[str] = Field(default=None, max_length=500)


class ArtifactVersionRestoreRequest(BaseModel):
    base_version: int = Field(ge=1)
    change_summary: Optional[str] = Field(default=None, max_length=500)
