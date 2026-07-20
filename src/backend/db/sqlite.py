"""Small SQLite document-store adapter used for zero-setup local runs.

It intentionally implements only the Motor collection operations used by this
project. Documents are stored as JSON while uniqueness and updates are guarded
by a process-wide lock and SQLite transactions.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Any


class SQLiteDuplicateKeyError(Exception):
    """Raised with the same semantics as pymongo DuplicateKeyError."""


_MISSING = object()


def _json_default(value: Any):
    if isinstance(value, datetime):
        return {"__reagent_datetime__": value.isoformat()}
    raise TypeError(f"Unsupported SQLite document value: {type(value).__name__}")


def _json_hook(value: dict):
    raw = value.get("__reagent_datetime__")
    if len(value) == 1 and raw:
        return datetime.fromisoformat(raw)
    return value


def _encode(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, default=_json_default)


def _decode(raw: str) -> dict:
    return json.loads(raw, object_hook=_json_hook)


def _get_path(document: dict, path: str, default: Any = _MISSING) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _set_path(document: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    current = document
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = deepcopy(value)


def _unset_path(document: dict, path: str) -> None:
    parts = path.split(".")
    current: Any = document
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _compare(value: Any, condition: Any) -> bool:
    if not isinstance(condition, dict) or not any(
        str(key).startswith("$") for key in condition
    ):
        if condition is None and value is _MISSING:
            return True
        return value is not _MISSING and value == condition

    for operator, expected in condition.items():
        if operator == "$options":
            continue
        if operator == "$exists":
            if (value is not _MISSING) != bool(expected):
                return False
        elif operator == "$in":
            if value is _MISSING or value not in expected:
                return False
        elif operator == "$ne":
            if value is not _MISSING and value == expected:
                return False
        elif operator in {"$gt", "$gte", "$lt", "$lte"}:
            if value is _MISSING or value is None:
                return False
            try:
                if operator == "$gt" and not value > expected:
                    return False
                if operator == "$gte" and not value >= expected:
                    return False
                if operator == "$lt" and not value < expected:
                    return False
                if operator == "$lte" and not value <= expected:
                    return False
            except TypeError:
                return False
        elif operator == "$regex":
            if value is _MISSING or value is None:
                return False
            flags = re.IGNORECASE if "i" in condition.get("$options", "") else 0
            if re.search(str(expected), str(value), flags) is None:
                return False
        else:
            raise NotImplementedError(f"Unsupported SQLite query operator: {operator}")
    return True


def _matches(document: dict, query: dict | None) -> bool:
    if not query:
        return True
    for key, condition in query.items():
        if key == "$or":
            if not any(_matches(document, branch) for branch in condition):
                return False
            continue
        if key.startswith("$"):
            raise NotImplementedError(f"Unsupported SQLite query operator: {key}")
        if not _compare(_get_path(document, key), condition):
            return False
    return True


def _project(document: dict, projection: dict | None) -> dict:
    if not projection:
        return deepcopy(document)
    included = [key for key, value in projection.items() if value and key != "_id"]
    if included:
        result: dict = {}
        for path in included:
            value = _get_path(document, path)
            if value is not _MISSING:
                _set_path(result, path, value)
        if projection.get("_id", 1) and "_id" in document:
            result["_id"] = document["_id"]
        return result
    result = deepcopy(document)
    for path, value in projection.items():
        if not value:
            _unset_path(result, path)
    return result


def _sort_value(value: Any):
    if value is _MISSING or value is None:
        return (-1, 0, "")
    if isinstance(value, datetime):
        return (0, 0, value.timestamp())
    if isinstance(value, (int, float)):
        return (0, 1, value)
    return (0, 2, str(value).casefold())


@dataclass
class InsertOneResult:
    inserted_id: int


@dataclass
class UpdateResult:
    matched_count: int = 0
    modified_count: int = 0
    upserted_id: int | None = None


@dataclass
class DeleteResult:
    deleted_count: int = 0


class SQLiteCursor:
    def __init__(self, documents: list[dict], projection: dict | None = None):
        self._documents = documents
        self._projection = projection
        self._skip = 0
        self._limit: int | None = None
        self._iter_documents: list[dict] | None = None
        self._iter_index = 0

    def sort(self, fields, direction: int | None = None):
        pairs = fields if isinstance(fields, list) else [(fields, direction or 1)]
        for field, order in reversed(pairs):
            self._documents.sort(
                key=lambda doc, name=field: _sort_value(_get_path(doc, name)),
                reverse=order < 0,
            )
        return self

    def skip(self, count: int):
        self._skip = max(0, count)
        return self

    def limit(self, count: int):
        self._limit = max(0, count)
        return self

    def _result(self, length: int | None = None) -> list[dict]:
        documents = self._documents[self._skip :]
        effective_limit = self._limit
        if length is not None:
            effective_limit = length if effective_limit is None else min(effective_limit, length)
        if effective_limit is not None:
            documents = documents[:effective_limit]
        return [_project(document, self._projection) for document in documents]

    async def to_list(self, length: int | None = None) -> list[dict]:
        return self._result(length)

    def __aiter__(self):
        self._iter_documents = self._result()
        self._iter_index = 0
        return self

    async def __anext__(self):
        documents = self._iter_documents or []
        if self._iter_index >= len(documents):
            raise StopAsyncIteration
        result = documents[self._iter_index]
        self._iter_index += 1
        return result


class SQLiteCollection:
    def __init__(self, database: "SQLiteDatabase", name: str):
        self.database = database
        self.name = name

    async def create_index(
        self,
        fields,
        *,
        unique: bool = False,
        partialFilterExpression: dict | None = None,
        name: str | None = None,
        **_kwargs,
    ) -> str:
        if unique:
            self.database.register_unique(
                self.name,
                tuple(field for field, _direction in fields),
                partialFilterExpression,
                name or "_".join(field for field, _direction in fields),
            )
        return name or "sqlite_document_index"

    def _all(self) -> list[dict]:
        return self.database.read_collection(self.name)

    async def insert_one(self, document: dict) -> InsertOneResult:
        with self.database.lock:
            candidate = deepcopy(document)
            self.database.ensure_unique(self.name, candidate)
            cursor = self.database.connection.execute(
                "INSERT INTO documents(collection_name, data) VALUES (?, ?)",
                (self.name, _encode(candidate)),
            )
            row_id = int(cursor.lastrowid)
            self.database.connection.commit()
            document.setdefault("_id", row_id)
            return InsertOneResult(row_id)

    async def find_one(
        self, query: dict, projection: dict | None = None, sort=None
    ) -> dict | None:
        documents = [doc for doc in self._all() if _matches(doc, query)]
        cursor = SQLiteCursor(documents, projection)
        if sort:
            cursor.sort(sort)
        results = await cursor.to_list(length=1)
        return results[0] if results else None

    def find(self, query: dict | None = None, projection: dict | None = None):
        documents = [doc for doc in self._all() if _matches(doc, query)]
        return SQLiteCursor(documents, projection)

    async def count_documents(self, query: dict | None = None) -> int:
        return sum(1 for doc in self._all() if _matches(doc, query))

    async def update_one(
        self, query: dict, update: dict, upsert: bool = False
    ) -> UpdateResult:
        with self.database.lock:
            rows = self.database.read_rows(self.name)
            for row_id, document in rows:
                if not _matches(document, query):
                    continue
                changed = self.database.apply_update(document, update, inserting=False)
                self.database.ensure_unique(self.name, document, exclude_id=row_id)
                if changed:
                    self.database.connection.execute(
                        "UPDATE documents SET data = ? WHERE id = ?",
                        (_encode(document), row_id),
                    )
                    self.database.connection.commit()
                return UpdateResult(matched_count=1, modified_count=int(changed))

            if not upsert:
                return UpdateResult()
            document = {
                key: deepcopy(value)
                for key, value in query.items()
                if not key.startswith("$")
                and not (isinstance(value, dict) and any(str(k).startswith("$") for k in value))
            }
            self.database.apply_update(document, update, inserting=True)
            self.database.ensure_unique(self.name, document)
            cursor = self.database.connection.execute(
                "INSERT INTO documents(collection_name, data) VALUES (?, ?)",
                (self.name, _encode(document)),
            )
            row_id = int(cursor.lastrowid)
            self.database.connection.commit()
            return UpdateResult(upserted_id=row_id)

    async def update_many(self, query: dict, update: dict) -> UpdateResult:
        matched = modified = 0
        with self.database.lock:
            for row_id, document in self.database.read_rows(self.name):
                if not _matches(document, query):
                    continue
                matched += 1
                changed = self.database.apply_update(document, update, inserting=False)
                self.database.ensure_unique(self.name, document, exclude_id=row_id)
                if changed:
                    modified += 1
                    self.database.connection.execute(
                        "UPDATE documents SET data = ? WHERE id = ?",
                        (_encode(document), row_id),
                    )
            self.database.connection.commit()
        return UpdateResult(matched_count=matched, modified_count=modified)

    async def delete_many(self, query: dict) -> DeleteResult:
        with self.database.lock:
            ids = [
                row_id
                for row_id, document in self.database.read_rows(self.name)
                if _matches(document, query)
            ]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                self.database.connection.execute(
                    f"DELETE FROM documents WHERE id IN ({placeholders})", ids
                )
                self.database.connection.commit()
            return DeleteResult(len(ids))


class SQLiteDatabase:
    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        self.lock = RLock()
        self.connection: sqlite3.Connection | None = None
        self._collections: dict[str, SQLiteCollection] = {}
        self._unique: dict[str, list[tuple[tuple[str, ...], dict | None, str]]] = {}

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_name TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS documents_collection ON documents(collection_name)"
        )
        self.connection.commit()

    def __getitem__(self, name: str) -> SQLiteCollection:
        if name not in self._collections:
            self._collections[name] = SQLiteCollection(self, name)
        return self._collections[name]

    async def command(self, name: str) -> dict:
        if name != "ping":
            raise NotImplementedError(name)
        self.connection.execute("SELECT 1").fetchone()
        return {"ok": 1}

    async def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def register_unique(
        self,
        collection: str,
        fields: tuple[str, ...],
        partial: dict | None,
        name: str,
    ) -> None:
        spec = (fields, partial, name)
        specs = self._unique.setdefault(collection, [])
        if spec not in specs:
            specs.append(spec)

    def read_rows(self, collection: str) -> list[tuple[int, dict]]:
        rows = self.connection.execute(
            "SELECT id, data FROM documents WHERE collection_name = ?", (collection,)
        ).fetchall()
        result = []
        for row_id, raw in rows:
            document = _decode(raw)
            document.setdefault("_id", row_id)
            result.append((int(row_id), document))
        return result

    def read_collection(self, collection: str) -> list[dict]:
        with self.lock:
            return [document for _row_id, document in self.read_rows(collection)]

    def ensure_unique(
        self, collection: str, candidate: dict, exclude_id: int | None = None
    ) -> None:
        for fields, partial, name in self._unique.get(collection, []):
            if partial and not _matches(candidate, partial):
                continue
            values = tuple(_get_path(candidate, field, None) for field in fields)
            for row_id, existing in self.read_rows(collection):
                if row_id == exclude_id or (partial and not _matches(existing, partial)):
                    continue
                existing_values = tuple(
                    _get_path(existing, field, None) for field in fields
                )
                if existing_values == values:
                    raise SQLiteDuplicateKeyError(
                        f"Duplicate key for {collection}.{name}: {values}"
                    )

    @staticmethod
    def apply_update(document: dict, update: dict, *, inserting: bool) -> bool:
        before = deepcopy(document)
        if not any(str(key).startswith("$") for key in update):
            document.clear()
            document.update(deepcopy(update))
            return document != before
        for path, value in update.get("$set", {}).items():
            _set_path(document, path, value)
        if inserting:
            for path, value in update.get("$setOnInsert", {}).items():
                _set_path(document, path, value)
        for path in update.get("$unset", {}):
            _unset_path(document, path)
        for path, amount in update.get("$inc", {}).items():
            current = _get_path(document, path, 0)
            _set_path(document, path, current + amount)
        return document != before

    async def prune_expired_events(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self["pipeline_events"].delete_many(
            {"expires_at": {"$lt": now}}
        )
        return result.deleted_count
