# backend/api/routes/stream.py — Pipeline execution + SSE endpoints.
#
# Outline:
#   POST /graph/stream/create           start pipeline async for project_id
#   POST /graph/stream/resume           submit interrupt feedback
#                                       (resume_type: accept|feedback|redo_artifact)
#   GET  /graph/stream/{project_id}     SSE event stream (EventSourceResponse)
#                                       Reconnection support:
#                                       - ?last_event_id=N query param, OR
#                                       - Last-Event-ID HTTP header (native
#                                         browser EventSource uses this)
#                                       On reconnect, events with _seq > N are
#                                       replayed before live-streaming new ones.
#                                       If project is in a terminal state with
#                                       no history (TTL expired), falls back to
#                                       a synthetic replay frame.
import json
from fastapi import APIRouter, Request, Header
from sse_starlette.sse import EventSourceResponse

from backend.models.requests import StreamCreateRequest, StreamResumeRequest
from backend.services.execution import ExecutionService
from backend.services.stream_manager import stream_manager
from backend.db.mongo import projects_col

router = APIRouter(prefix="/graph", tags=["stream"])
exec_svc = ExecutionService()


@router.post("/stream/create")
async def stream_create(req: StreamCreateRequest):
    """Start the RE pipeline. Subscribe to GET /graph/stream/{project_id} for events."""
    # Fetch project config from DB
    project = await projects_col().find_one(
        {"project_id": req.project_id}, {"_id": 0}
    )
    if not project:
        return {"error": "Project not found"}

    config = {
        "project_name": project["project_name"],
        "description": project["description"],
        "srs_template": project.get("srs_template"),
        "srs_example_path": project.get("srs_example_path") or "src/util/doc_template/document_example.md",
    }

    # Allow override from request
    if req.human_request:
        config["description"] += f"\n\n补充说明: {req.human_request}"

    try:
        await exec_svc.start(req.project_id, config)
    except RuntimeError as e:
        return {"error": str(e), "status": "rejected"}
    return {"status": "started", "project_id": req.project_id}


@router.post("/stream/resume")
async def stream_resume(req: StreamResumeRequest):
    """Submit user feedback to unblock the paused worker thread."""
    return await exec_svc.resume(
        project_id=req.project_id,
        resume_type=req.resume_type,
        human_comment=req.human_comment,
        target_artifact=req.target_artifact,
        prune_downstream=req.prune_downstream,
    )


async def _terminal_state_stream(project: dict):
    """Yield a synthetic replay event for clients reconnecting after the
    pipeline has already completed, finished, or errored, then close."""
    project_id = project.get("project_id")
    status = project.get("status")
    yield {
        "event": "connected",
        "data": json.dumps({"type": "connected", "project_id": project_id},
                           ensure_ascii=False),
    }
    if status in ("completed", "finished"):
        completed_payload = {
            "type": "completed",
            "project_id": project_id,
            "status": "completed",
            "replay": True,
            "total_artifacts": 17,
            "srs_generated": True,
        }
        yield {
            "event": "completed",
            "data": json.dumps(completed_payload, ensure_ascii=False),
        }
        yield {
            "event": "finished",
            "data": json.dumps(
                {**completed_payload, "type": "finished"},
                ensure_ascii=False,
            ),
        }
    elif status == "cancelled":
        yield {
            "event": "cancelled",
            "data": json.dumps(
                {"type": "cancelled", "project_id": project_id, "replay": True,
                 "reason": project.get("last_error") or "Pipeline was cancelled"},
                ensure_ascii=False,
            ),
        }
    else:  # error
        yield {
            "event": "error",
            "data": json.dumps(
                {"type": "error", "project_id": project_id, "replay": True,
                 "error": project.get("last_error") or "Unknown error",
                 "stage": project.get("current_stage"),
                 "recoverable": False},
                ensure_ascii=False,
            ),
        }


def _parse_last_event_id(value: str | None) -> int | None:
    """Parse an incoming Last-Event-ID header or query param into an int."""
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@router.get("/stream/{project_id}")
async def stream_events(
    project_id: str,
    request: Request,
    last_event_id: int | None = None,
    last_event_id_header: str | None = Header(None, alias="Last-Event-ID"),
):
    """SSE endpoint. Supports reconnection via ``?last_event_id=N`` query
    param or the standard ``Last-Event-ID`` header (browser's native
    ``EventSource`` sets this automatically on reconnect).

    Event id semantics:
      - Every event carries a per-project monotonic ``_seq`` field.
      - The SSE ``id:`` line exposes it so browsers remember it.
      - On reconnect, events with ``_seq > last_event_id`` are replayed
        from the in-memory history ring buffer, then live-streaming resumes.

    Terminal-state fallback:
      - If the project already completed/finished/errored AND history was pruned by
        TTL, the new ``subscribe()`` still returns "No active session".
      - For that edge case we read the project doc and emit a synthetic
        replay frame so the client gets a final answer instead of hanging.
    """
    # Prefer explicit query param over header; then fallback to header.
    if last_event_id is None:
        last_event_id = _parse_last_event_id(last_event_id_header)

    # Live/history path: delegate to stream_manager with reconnection support.
    if stream_manager.has_queue(project_id) or stream_manager.has_history(project_id):
        return EventSourceResponse(
            stream_manager.subscribe(project_id, last_event_id=last_event_id)
        )

    # Fallback: no in-memory state. Check DB for terminal-state replay.
    project = await projects_col().find_one(
        {"project_id": project_id}, {"_id": 0}
    )
    if project and project.get("status") in ("completed", "finished", "error", "cancelled"):
        return EventSourceResponse(_terminal_state_stream(project))

    # Truly unknown project — the subscribe generator will emit an error.
    return EventSourceResponse(
        stream_manager.subscribe(project_id, last_event_id=last_event_id)
    )
