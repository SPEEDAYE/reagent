# backend/api/routes/artifacts.py — Artifact retrieval + PDF export.
#
# Outline:
#   GET  /artifacts/{project_id}                  list all 17 artifacts + DAG
#   GET  /artifacts/{project_id}/{artifact_name}  single artifact markdown
#   POST /artifacts/export_pdf                    naive markdown → PDF via
#                                                 reportlab (headings + text;
#                                                 no Mermaid rendering)
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from backend.services.artifact_service import ArtifactService
from backend.services.artifact_version_service import (
    ArtifactVersionConflict,
    ArtifactVersionNotFound,
    ArtifactVersionService,
)
from backend.models.requests import (
    ArtifactVersionCreateRequest,
    ArtifactVersionRestoreRequest,
    ExportPdfRequest,
)
from backend.auth import CurrentUser, optional_current_user, require_project_owner
from backend.services.run_service import RunService

router = APIRouter(prefix="/artifacts", tags=["artifacts"])
svc = ArtifactService()
run_svc = RunService()
version_svc = ArtifactVersionService()


async def _selected_run_id(project: dict, requested_run_id: str | None) -> str | None:
    run_id = requested_run_id or project.get("current_run_id")
    if requested_run_id and not await run_svc.get(project["project_id"], requested_run_id):
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run_id


def _artifact_file(project_id: str, artifact_name: str, run_id: str | None) -> dict:
    data = svc.get_content(project_id, artifact_name, run_id)
    if data.get("error"):
        raise HTTPException(status_code=404, detail=data["error"])
    return data


def _actor_id(current_user: CurrentUser | None, project: dict) -> str:
    return current_user.user_id if current_user else project["user_id"]


def _version_error(error: Exception) -> HTTPException:
    if isinstance(error, ArtifactVersionConflict):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=404, detail=str(error))


@router.get("/{project_id}")
async def list_artifacts(
    project_id: str,
    run_id: str | None = Query(None, pattern=r"^[a-f0-9]{12}$"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """List all artifacts with DAG dependency data and progress stats."""
    project = await require_project_owner(project_id, current_user)
    selected_run_id = await _selected_run_id(project, run_id)
    result = svc.list_all(project_id, selected_run_id)
    latest = await version_svc.latest_by_artifact(project_id, selected_run_id)
    for artifact in result["artifacts"]:
        version = latest.get(artifact["artifact_name"])
        if not version:
            continue
        artifact.update(
            {
                "status": "completed",
                "content_preview": version["content"][:200],
                "current_version": version["version"],
                "content_hash": version["content_hash"],
                "version_source": version["source"],
            }
        )
    result["completed"] = sum(
        1 for artifact in result["artifacts"] if artifact["status"] == "completed"
    )
    result["pending"] = result["total"] - result["completed"]
    return result


@router.get("/{project_id}/{artifact_name}")
async def get_artifact(
    project_id: str,
    artifact_name: str,
    run_id: str | None = Query(None, pattern=r"^[a-f0-9]{12}$"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """Get full content of a single artifact."""
    project = await require_project_owner(project_id, current_user)
    selected_run_id = await _selected_run_id(project, run_id)
    data = _artifact_file(project_id, artifact_name, selected_run_id)
    latest = await version_svc.latest(
        project_id,
        selected_run_id,
        artifact_name,
        baseline_content=data.get("content", ""),
    )
    if latest:
        data.update(
            {
                "content": latest["content"],
                "status": "completed",
                "current_version": latest["version"],
                "content_hash": latest["content_hash"],
                "version_source": latest["source"],
            }
        )
    return data


@router.get("/{project_id}/{artifact_name}/versions")
async def list_artifact_versions(
    project_id: str,
    artifact_name: str,
    run_id: str | None = Query(None, pattern=r"^[a-f0-9]{12}$"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    project = await require_project_owner(project_id, current_user)
    selected_run_id = await _selected_run_id(project, run_id)
    data = _artifact_file(project_id, artifact_name, selected_run_id)
    versions = await version_svc.list_versions(
        project_id,
        selected_run_id,
        artifact_name,
        baseline_content=data.get("content", ""),
    )
    return {
        "project_id": project_id,
        "run_id": selected_run_id,
        "artifact_name": artifact_name,
        "current_version": versions[0]["version"] if versions else None,
        "versions": versions,
    }


@router.post("/{project_id}/{artifact_name}/versions", status_code=201)
async def create_artifact_version(
    project_id: str,
    artifact_name: str,
    req: ArtifactVersionCreateRequest,
    run_id: str | None = Query(None, pattern=r"^[a-f0-9]{12}$"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    project = await require_project_owner(project_id, current_user)
    selected_run_id = await _selected_run_id(project, run_id)
    data = _artifact_file(project_id, artifact_name, selected_run_id)
    try:
        saved = await version_svc.create_version(
            project_id,
            selected_run_id,
            artifact_name,
            req.content,
            _actor_id(current_user, project),
            baseline_content=data.get("content", ""),
            base_version=req.base_version,
            based_on_version=req.based_on_version,
            change_summary=req.change_summary,
        )
        svc.write_content(
            project_id, artifact_name, saved["content"], selected_run_id
        )
        return saved
    except ArtifactVersionConflict as error:
        raise _version_error(error) from error


@router.get("/{project_id}/{artifact_name}/versions/compare")
async def compare_artifact_versions(
    project_id: str,
    artifact_name: str,
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
    run_id: str | None = Query(None, pattern=r"^[a-f0-9]{12}$"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    project = await require_project_owner(project_id, current_user)
    selected_run_id = await _selected_run_id(project, run_id)
    data = _artifact_file(project_id, artifact_name, selected_run_id)
    await version_svc.ensure_baseline(
        project_id, selected_run_id, artifact_name, data.get("content", "")
    )
    try:
        return await version_svc.compare_versions(
            project_id,
            selected_run_id,
            artifact_name,
            from_version,
            to_version,
        )
    except ArtifactVersionNotFound as error:
        raise _version_error(error) from error


@router.get("/{project_id}/{artifact_name}/versions/{version}")
async def get_artifact_version(
    project_id: str,
    artifact_name: str,
    version: int,
    run_id: str | None = Query(None, pattern=r"^[a-f0-9]{12}$"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    project = await require_project_owner(project_id, current_user)
    selected_run_id = await _selected_run_id(project, run_id)
    data = _artifact_file(project_id, artifact_name, selected_run_id)
    await version_svc.ensure_baseline(
        project_id, selected_run_id, artifact_name, data.get("content", "")
    )
    try:
        return await version_svc.get_version(
            project_id, selected_run_id, artifact_name, version
        )
    except ArtifactVersionNotFound as error:
        raise _version_error(error) from error


@router.post("/{project_id}/{artifact_name}/versions/{version}/restore", status_code=201)
async def restore_artifact_version(
    project_id: str,
    artifact_name: str,
    version: int,
    req: ArtifactVersionRestoreRequest,
    run_id: str | None = Query(None, pattern=r"^[a-f0-9]{12}$"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    project = await require_project_owner(project_id, current_user)
    selected_run_id = await _selected_run_id(project, run_id)
    data = _artifact_file(project_id, artifact_name, selected_run_id)
    await version_svc.ensure_baseline(
        project_id, selected_run_id, artifact_name, data.get("content", "")
    )
    try:
        restored = await version_svc.restore_version(
            project_id,
            selected_run_id,
            artifact_name,
            version,
            _actor_id(current_user, project),
            baseline_content=data.get("content", ""),
            base_version=req.base_version,
            change_summary=req.change_summary,
        )
        svc.write_content(
            project_id, artifact_name, restored["content"], selected_run_id
        )
        return restored
    except (ArtifactVersionConflict, ArtifactVersionNotFound) as error:
        raise _version_error(error) from error


@router.post("/export_pdf")
async def export_pdf(
    req: ExportPdfRequest,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """Export an artifact as PDF."""
    project = await require_project_owner(req.project_id, current_user)
    selected_run_id = await _selected_run_id(project, req.run_id)
    data = _artifact_file(req.project_id, req.artifact_name, selected_run_id)
    latest = await version_svc.latest(
        req.project_id,
        selected_run_id,
        req.artifact_name,
        baseline_content=data.get("content", ""),
    )
    if latest:
        data["content"] = latest["content"]
    content = data.get("content", "")
    if not content:
        return {"error": "Artifact has no content"}

    # Simple markdown-to-PDF using reportlab (basic text rendering)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=2 * cm, bottomMargin=2 * cm)
        styles = getSampleStyleSheet()
        story = []
        for line in content.split("\n"):
            if line.startswith("# "):
                story.append(Paragraph(line[2:], styles["Heading1"]))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], styles["Heading2"]))
            elif line.startswith("### "):
                story.append(Paragraph(line[4:], styles["Heading3"]))
            elif line.strip():
                story.append(Paragraph(line, styles["Normal"]))
            else:
                story.append(Spacer(1, 0.3 * cm))
        doc.build(story)
        buffer.seek(0)

        filename = f"{req.artifact_name}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ImportError:
        return {"error": "reportlab not installed. Run: pip install reportlab"}
