# backend/db/mongo.py — Async MongoDB client (motor).
#
# Outline:
#   connect_db()          create AsyncIOMotorClient at startup
#   close_db()            close client at shutdown
#   get_db()              return module-level db handle
#   projects_col()        projects collection
#   artifacts_col()       artifacts collection (currently unused — writes go
#                         to filesystem; still referenced by delete cascade)
#   files_col()           files collection (upload metadata)
from motor.motor_asyncio import AsyncIOMotorClient
from backend.config import settings

_client: AsyncIOMotorClient | None = None
_db = None


async def connect_db():
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client[settings.DB_NAME]


async def close_db():
    global _client
    if _client:
        _client.close()


def get_db():
    return _db


def projects_col():
    return _db["projects"]


def artifacts_col():
    return _db["artifacts"]


def files_col():
    return _db["files"]
