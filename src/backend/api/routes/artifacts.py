# backend/api/routes/artifacts.py — Artifact retrieval + PDF export.
#
# Outline:
#   GET  /artifacts/{project_id}                  list all 17 artifacts + DAG
#   GET  /artifacts/{project_id}/{artifact_name}  single artifact markdown
#   POST /artifacts/export_pdf                    naive markdown → PDF via
#                                                 reportlab (headings + text;
#                                                 no Mermaid rendering)
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import io

from backend.services.artifact_service import ArtifactService
from backend.models.requests import ExportPdfRequest

router = APIRouter(prefix="/artifacts", tags=["artifacts"])
svc = ArtifactService()


@router.get("/{project_id}")
async def list_artifacts(project_id: str):
    """List all artifacts with DAG dependency data and progress stats."""
    return svc.list_all(project_id)


@router.get("/{project_id}/{artifact_name}")
async def get_artifact(project_id: str, artifact_name: str):
    """Get full content of a single artifact."""
    return svc.get_content(project_id, artifact_name)


@router.post("/export_pdf")
async def export_pdf(req: ExportPdfRequest):
    """Export an artifact as PDF."""
    data = svc.get_content(req.project_id, req.artifact_name)
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
