# backend/api/routes/__init__.py — Route registration aggregator.
# register_routes(app) mounts: health, project, stream, artifacts, files routers.
from fastapi import FastAPI
from backend.api.routes.health import router as health_router
from backend.api.routes.project import router as project_router
from backend.api.routes.stream import router as stream_router
from backend.api.routes.artifacts import router as artifacts_router
from backend.api.routes.files import router as files_router


def register_routes(app: FastAPI):
    app.include_router(health_router)
    app.include_router(project_router)
    app.include_router(stream_router)
    app.include_router(artifacts_router)
    app.include_router(files_router)
