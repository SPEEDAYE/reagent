# backend/api/routes/project.py — Project CRUD endpoints.
#
# Outline:
#   POST   /project/create              create project (returns project_id)
#   GET    /project/list/{user_id}      list user's projects (latest first)
#   GET    /project/active/{user_id}    the project a returning user should
#                                       resume (running/interrupted, else latest)
#   GET    /project/{project_id}        fetch single project doc
#   DELETE /project/{project_id}        cascade delete: projects + artifacts
#                                       + files + upload_dir + output_dir
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.auth import (
    CurrentUser,
    optional_current_user,
    require_project_owner,
    resolve_user_id,
)
from backend.models.requests import ProjectCreateRequest, ProjectUpdateRequest
from backend.services.project_service import ProjectService
from backend.services.run_service import RunService
from backend.services.event_service import EventService

router = APIRouter(prefix="/project", tags=["project"])
svc = ProjectService()
run_svc = RunService()
event_svc = EventService()


@router.post("/create")
async def create_project(
    req: ProjectCreateRequest,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    data = req.model_dump()
    data["user_id"] = resolve_user_id(current_user, req.user_id)
    return await svc.create(data)


@router.get("/list")
async def list_my_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
    status_filter: str | None = Query(None, alias="status"),
    archived: bool | None = Query(False),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user_id: str | None = Query(None, description="Temporary compatibility field"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """List projects owned by the authenticated user."""
    owner_id = resolve_user_id(current_user, user_id)
    statuses = [item for item in (status_filter or "").split(",") if item]
    return await svc.list_by_user(
        owner_id,
        page=page,
        page_size=page_size,
        search=q,
        statuses=statuses,
        archived=archived,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/list/{user_id}")
async def list_projects(
    user_id: str,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """Deprecated path-based listing; retained during frontend migration."""
    owner_id = resolve_user_id(current_user, user_id)
    return await svc.list_by_user(owner_id, page_size=100)


@router.get("/active")
async def my_active_project(
    user_id: str | None = Query(None, description="Temporary compatibility field"),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """Return the authenticated user's resumable or latest project."""
    owner_id = resolve_user_id(current_user, user_id)
    return await svc.active_for_user(owner_id)


@router.get("/active/{user_id}")
async def active_project(
    user_id: str,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """The project a returning user should resume. Lets the frontend rediscover
    its running/last project from the server instead of relying on localStorage."""
    owner_id = resolve_user_id(current_user, user_id)
    return await svc.active_for_user(owner_id)


@router.get("/{project_id}/runs")
async def list_project_runs(
    project_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    """List immutable execution records for one owned project."""
    await require_project_owner(project_id, current_user)
    return await run_svc.list_by_project(project_id, limit=limit)


@router.get("/{project_id}/runs/{run_id}")
async def get_project_run(
    project_id: str,
    run_id: str,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    await require_project_owner(project_id, current_user)
    run = await run_svc.get(project_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.get("/{project_id}/runs/{run_id}/events")
async def get_run_events(
    project_id: str,
    run_id: str,
    after: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    await require_project_owner(project_id, current_user)
    run = await run_svc.get(project_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    events = await event_svc.list_after(run_id, after_event_id=after, limit=limit)
    return {"project_id": project_id, "run_id": run_id, "events": events}


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    return await require_project_owner(project_id, current_user)


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    req: ProjectUpdateRequest,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    await require_project_owner(project_id, current_user)
    return await svc.update(project_id, req.model_dump())


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: CurrentUser | None = Depends(optional_current_user),
):
    await require_project_owner(project_id, current_user)
    return await svc.delete(project_id)
