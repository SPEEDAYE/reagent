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
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sse_starlette.sse import EventSourceResponse

from backend.models.requests import (
    StreamCancelRequest,
    StreamCreateRequest,
    StreamResumeRequest,
)
from backend.services.execution import ExecutionService
from backend.services.stream_manager import stream_manager
from backend.services.run_service import RunQuotaExceeded, RunService
from backend.services.event_service import EventService
from backend.auth import CurrentUser, optional_current_user, require_project_owner, resolve_user_id

router = APIRouter(prefix="/graph", tags=["stream"])
exec_svc = ExecutionService()
run_svc = RunService()
event_svc = EventService()


@router.post("/stream/create")
async def stream_create(
    req: StreamCreateRequest,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """Start the RE pipeline. Subscribe to GET /graph/stream/{project_id} for events."""
    # Fetch project config from DB
    if req.user_id:
        resolve_user_id(current_user, req.user_id)
    project = await require_project_owner(req.project_id, current_user)

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
        run = await run_svc.create(project, config)
    except RunQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    run_id = run["run_id"]
    try:
        await exec_svc.start(req.project_id, config, run_id=run_id)
    except RuntimeError as e:
        await run_svc.update_status(run_id, status="rejected", last_error=str(e))
        return {
            "error": str(e),
            "status": "rejected",
            "project_id": req.project_id,
            "run_id": run_id,
        }
    return {
        "status": "started",
        "project_id": req.project_id,
        "run_id": run_id,
    }


@router.post("/stream/resume")
async def stream_resume(
    req: StreamResumeRequest,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """Submit user feedback to unblock the paused worker thread."""
    await require_project_owner(req.project_id, current_user)
    try:
        return await exec_svc.resume(
            project_id=req.project_id,
            resume_type=req.resume_type,
            human_comment=req.human_comment,
            target_artifact=req.target_artifact,
            prune_downstream=req.prune_downstream,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/stream/cancel")
async def stream_cancel(
    req: StreamCancelRequest,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    await require_project_owner(req.project_id, current_user)
    return await exec_svc.cancel(req.project_id)


async def _terminal_state_stream(project: dict):
    """Yield a synthetic replay event for clients reconnecting after the
    pipeline has already completed, finished, or errored, then close."""
    project_id = project.get("project_id")
    run_id = project.get("current_run_id")
    status = project.get("status")
    yield {
        "event": "connected",
        "data": json.dumps({"type": "connected", "project_id": project_id,
                            "run_id": run_id},
                           ensure_ascii=False),
    }
    if status in ("completed", "finished"):
        completed_payload = {
            "type": "completed",
            "project_id": project_id,
            "run_id": run_id,
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
                {"type": "cancelled", "project_id": project_id,
                 "run_id": run_id, "replay": True,
                 "reason": project.get("last_error") or "Pipeline was cancelled"},
                ensure_ascii=False,
            ),
        }
    else:  # error
        yield {
            "event": "error",
            "data": json.dumps(
                {"type": "error", "project_id": project_id,
                 "run_id": run_id, "replay": True,
                 "error": project.get("last_error") or "Unknown error",
                 "stage": project.get("current_stage"),
                 "recoverable": False},
                ensure_ascii=False,
            ),
        }


async def _persisted_replay_stream(
    project: dict,
    events: list[dict],
    last_event_id: int | None,
):
    """Replay database-backed events when process memory is unavailable."""
    project_id = project.get("project_id")
    run_id = project.get("current_run_id")
    yield {
        "event": "connected",
        "data": json.dumps(
            {
                "type": "connected",
                "project_id": project_id,
                "run_id": run_id,
                "resume": last_event_id is not None,
                "last_event_id": last_event_id or 0,
                "persisted_replay": True,
            },
            ensure_ascii=False,
        ),
    }
    terminal_seen = False
    for event in events:
        event_type = event.get("type", "message")
        terminal_seen = terminal_seen or event_type in {
            "completed", "finished", "cancelled"
        } or (event_type == "error" and not event.get("recoverable", False))
        yield {
            "event": event_type,
            "id": str(event.get("_seq", "")),
            "data": json.dumps(event, ensure_ascii=False),
        }

    # On a first connection, synthesize a terminal frame if a restart changed
    # database status but no terminal event had time to persist. A reconnect
    # already at the tail only receives the connected frame and closes.
    if not terminal_seen and last_event_id is None and project.get("status") in {
        "completed", "finished", "error", "cancelled"
    }:
        first = True
        async for frame in _terminal_state_stream(project):
            if first:
                first = False
                continue
            yield frame


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
    current_user: CurrentUser | None = Depends(optional_current_user),
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
    # Authorize before consulting in-memory stream state so a foreign project
    # cannot be discovered through SSE behavior.
    project = await require_project_owner(project_id, current_user)

    # Prefer explicit query param over header; then fallback to header.
    if last_event_id is None:
        last_event_id = _parse_last_event_id(last_event_id_header)

    # Live/history path: delegate to stream_manager with reconnection support.
    if stream_manager.has_queue(project_id) or stream_manager.has_history(project_id):
        return EventSourceResponse(
            stream_manager.subscribe(project_id, last_event_id=last_event_id)
        )

    # Fallback: no in-memory state. Check DB for terminal-state replay.
    run_id = project.get("current_run_id")
    if run_id:
        persisted_events = await event_svc.list_after(
            run_id, after_event_id=last_event_id or 0
        )
        if persisted_events or project.get("status") in (
            "completed", "finished", "error", "cancelled"
        ):
            return EventSourceResponse(
                _persisted_replay_stream(project, persisted_events, last_event_id)
            )

    if project and project.get("status") in ("completed", "finished", "error", "cancelled"):
        return EventSourceResponse(_terminal_state_stream(project))

    # Truly unknown project — the subscribe generator will emit an error.
    return EventSourceResponse(
        stream_manager.subscribe(project_id, last_event_id=last_event_id)
    )
