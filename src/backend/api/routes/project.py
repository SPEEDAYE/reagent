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
from fastapi import APIRouter
from backend.models.requests import ProjectCreateRequest
from backend.services.project_service import ProjectService

router = APIRouter(prefix="/project", tags=["project"])
svc = ProjectService()


@router.post("/create")
async def create_project(req: ProjectCreateRequest):
    return await svc.create(req.model_dump())


@router.get("/list/{user_id}")
async def list_projects(user_id: str):
    return await svc.list_by_user(user_id)


@router.get("/active/{user_id}")
async def active_project(user_id: str):
    """The project a returning user should resume. Lets the frontend rediscover
    its running/last project from the server instead of relying on localStorage."""
    return await svc.active_for_user(user_id)


@router.get("/{project_id}")
async def get_project(project_id: str):
    return await svc.get(project_id)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    return await svc.delete(project_id)
