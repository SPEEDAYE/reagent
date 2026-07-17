# backend/main.py — FastAPI application bootstrap.
#
# Outline:
#   app                       FastAPI instance (title="REagent API", v1.0.0)
#   CORSMiddleware            allow_origins=settings.CORS_ORIGINS ("*")
#   startup()                 on_event startup: connect MongoDB + capture
#                             the main event loop for StreamManager
#                             (critical so worker threads can schedule coroutines)
#   shutdown()                on_event shutdown: close MongoDB
#   register_routes(app)      mounts health, project, stream, artifacts, files routers
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import register_routes
from backend.db.mongo import connect_db, close_db
from backend.services.stream_manager import stream_manager
from backend.config import settings

app = FastAPI(
    title="REagent API",
    version="1.0.0",
    description="REagent 1.0 Requirements Engineering Automation API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await connect_db()
    stream_manager.set_loop(asyncio.get_event_loop())


@app.on_event("shutdown")
async def shutdown():
    await close_db()


register_routes(app)
