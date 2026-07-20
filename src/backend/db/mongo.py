"""Database facade.

SQLite is the zero-setup default. The historical module name and collection
helpers remain stable so the service layer works with either SQLite or MongoDB.
"""

from __future__ import annotations

from backend.config import settings
from backend.db.sqlite import SQLiteDatabase, SQLiteDuplicateKeyError

ASCENDING = 1
DESCENDING = -1


class _FallbackDuplicateKeyError(Exception):
    pass


# Services import this symbol instead of importing pymongo directly, allowing
# the default SQLite installation to omit MongoDB drivers entirely.
DuplicateKeyError = SQLiteDuplicateKeyError
_duplicate_key_types: tuple[type[Exception], ...] = (SQLiteDuplicateKeyError,)

_client = None
_db = None


async def connect_db():
    global _client, _db, DuplicateKeyError, _duplicate_key_types
    database_type = settings.DATABASE_TYPE.lower()
    if database_type == "sqlite":
        _client = None
        _db = SQLiteDatabase(settings.SQLITE_PATH)
        await _db.initialize()
        DuplicateKeyError = SQLiteDuplicateKeyError
        _duplicate_key_types = (SQLiteDuplicateKeyError,)
    elif database_type in {"mongo", "mongodb"}:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError
        except ImportError as exc:
            raise RuntimeError(
                "MongoDB mode requires: pip install -r requirements-mongo.txt"
            ) from exc
        _client = AsyncIOMotorClient(settings.MONGODB_URI)
        _db = _client[settings.DB_NAME]
        DuplicateKeyError = MongoDuplicateKeyError
        _duplicate_key_types = (SQLiteDuplicateKeyError, MongoDuplicateKeyError)
    else:
        raise RuntimeError(
            f"Unsupported DATABASE_TYPE={settings.DATABASE_TYPE!r}; use sqlite or mongodb"
        )

    await _create_indexes()
    if database_type == "sqlite":
        await _db.prune_expired_events()
    print(f"[database] {database_type} ready")


def is_duplicate_key_error(error: BaseException) -> bool:
    return isinstance(error, _duplicate_key_types)


async def _create_indexes():
    await _db["projects"].create_index(
        [("project_id", ASCENDING)], unique=True, name="project_id_unique"
    )
    await _db["projects"].create_index(
        [("user_id", ASCENDING), ("updated_at", DESCENDING)],
        name="user_projects_recent",
    )
    await _db["projects"].create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
        name="user_projects_status_recent",
    )
    await _db["pipeline_runs"].create_index(
        [("run_id", ASCENDING)], unique=True, name="run_id_unique"
    )
    await _db["pipeline_runs"].create_index(
        [("project_id", ASCENDING), ("created_at", DESCENDING)],
        name="project_runs_recent",
    )
    await _db["pipeline_runs"].create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
        name="user_runs_status_recent",
    )
    await _db["pipeline_runs"].create_index(
        [("user_id", ASCENDING), ("active_slot", ASCENDING)],
        unique=True,
        partialFilterExpression={"active_slot": {"$exists": True}},
        name="user_active_slot_unique",
    )
    await _db["pipeline_events"].create_index(
        [("run_id", ASCENDING), ("event_id", ASCENDING)],
        unique=True,
        name="run_event_unique",
    )
    await _db["pipeline_events"].create_index(
        [("project_id", ASCENDING), ("created_at", ASCENDING)],
        name="project_events_ordered",
    )
    await _db["pipeline_events"].create_index(
        [("expires_at", ASCENDING)],
        expireAfterSeconds=0,
        name="events_ttl",
    )
    await _db["artifact_versions"].create_index(
        [
            ("project_id", ASCENDING),
            ("run_id", ASCENDING),
            ("artifact_name", ASCENDING),
            ("version", ASCENDING),
        ],
        unique=True,
        name="artifact_version_unique",
    )
    await _db["artifact_versions"].create_index(
        [
            ("project_id", ASCENDING),
            ("run_id", ASCENDING),
            ("artifact_name", ASCENDING),
            ("version", DESCENDING),
        ],
        name="artifact_versions_recent",
    )


async def close_db():
    global _client, _db
    if settings.DATABASE_TYPE.lower() == "sqlite" and _db is not None:
        await _db.close()
    elif _client is not None:
        _client.close()
    _client = None
    _db = None


def get_db():
    return _db


def projects_col():
    return _db["projects"]


def artifacts_col():
    return _db["artifacts"]


def files_col():
    return _db["files"]


def pipeline_runs_col():
    return _db["pipeline_runs"]


def pipeline_events_col():
    return _db["pipeline_events"]


def artifact_versions_col():
    return _db["artifact_versions"]
