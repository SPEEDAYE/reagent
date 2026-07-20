"""Mongo-backed, immutable artifact version history.

Generated files remain untouched. User edits and restores are stored as an
overlay scoped by project, pipeline run and artifact name.
"""

from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib

from backend.db.mongo import artifact_versions_col, is_duplicate_key_error


class ArtifactVersionConflict(Exception):
    pass


class ArtifactVersionNotFound(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _scope(project_id: str, run_id: str | None, artifact_name: str) -> dict:
    return {
        "project_id": project_id,
        "run_id": run_id,
        "artifact_name": artifact_name,
    }


def _public(doc: dict | None, include_content: bool = True) -> dict | None:
    if not doc:
        return None
    result = {key: value for key, value in doc.items() if key != "_id"}
    if not include_content:
        result.pop("content", None)
    return result


class ArtifactVersionService:
    async def ensure_baseline(
        self,
        project_id: str,
        run_id: str | None,
        artifact_name: str,
        content: str,
    ) -> dict | None:
        """Lazily register generated filesystem content as immutable v1."""
        query = _scope(project_id, run_id, artifact_name)
        existing = await artifact_versions_col().find_one(query, sort=[("version", -1)])
        if existing or not content:
            return _public(existing)

        now = _utcnow()
        baseline = {
            **query,
            "version": 1,
            "content": content,
            "content_hash": _hash(content),
            "source": "generated",
            "change_summary": "流水线生成的原始版本",
            "created_by": "system",
            "created_at": now,
            "based_on_version": None,
            "restored_from_version": None,
        }
        try:
            await artifact_versions_col().insert_one(baseline)
            return _public(baseline)
        except Exception as error:
            if not is_duplicate_key_error(error):
                raise
            return _public(
                await artifact_versions_col().find_one(query, sort=[("version", -1)])
            )

    async def latest(
        self,
        project_id: str,
        run_id: str | None,
        artifact_name: str,
        baseline_content: str = "",
    ) -> dict | None:
        await self.ensure_baseline(project_id, run_id, artifact_name, baseline_content)
        doc = await artifact_versions_col().find_one(
            _scope(project_id, run_id, artifact_name), sort=[("version", -1)]
        )
        return _public(doc)

    async def latest_by_artifact(
        self, project_id: str, run_id: str | None
    ) -> dict[str, dict]:
        cursor = artifact_versions_col().find(
            {"project_id": project_id, "run_id": run_id}
        ).sort([("artifact_name", 1), ("version", -1)])
        result: dict[str, dict] = {}
        async for doc in cursor:
            name = doc["artifact_name"]
            if name not in result:
                result[name] = _public(doc) or {}
        return result

    async def list_versions(
        self,
        project_id: str,
        run_id: str | None,
        artifact_name: str,
        baseline_content: str = "",
    ) -> list[dict]:
        await self.ensure_baseline(project_id, run_id, artifact_name, baseline_content)
        cursor = artifact_versions_col().find(
            _scope(project_id, run_id, artifact_name), {"content": 0}
        ).sort("version", -1)
        return [_public(doc, include_content=False) async for doc in cursor]

    async def get_version(
        self, project_id: str, run_id: str | None, artifact_name: str, version: int
    ) -> dict:
        doc = await artifact_versions_col().find_one(
            {**_scope(project_id, run_id, artifact_name), "version": version}
        )
        if not doc:
            raise ArtifactVersionNotFound(f"Artifact version v{version} not found")
        return _public(doc) or {}

    async def create_version(
        self,
        project_id: str,
        run_id: str | None,
        artifact_name: str,
        content: str,
        actor_id: str,
        *,
        baseline_content: str = "",
        base_version: int | None,
        based_on_version: int | None = None,
        change_summary: str | None = None,
        source: str = "edited",
        restored_from_version: int | None = None,
    ) -> dict:
        latest = await self.latest(
            project_id, run_id, artifact_name, baseline_content=baseline_content
        )
        latest_version = latest["version"] if latest else None
        if latest_version is not None and base_version != latest_version:
            raise ArtifactVersionConflict(
                f"Version conflict: latest is v{latest_version}, requested base is "
                f"v{base_version or 'none'}"
            )
        if latest and latest.get("content_hash") == _hash(content):
            return {**latest, "unchanged": True}

        version = (latest_version or 0) + 1
        now = _utcnow()
        doc = {
            **_scope(project_id, run_id, artifact_name),
            "version": version,
            "content": content,
            "content_hash": _hash(content),
            "source": source,
            "change_summary": change_summary or (
                "恢复历史版本" if source == "restored" else "人工编辑"
            ),
            "created_by": actor_id,
            "created_at": now,
            "based_on_version": based_on_version or latest_version,
            "restored_from_version": restored_from_version,
        }
        try:
            await artifact_versions_col().insert_one(doc)
        except Exception as exc:
            if not is_duplicate_key_error(exc):
                raise
            raise ArtifactVersionConflict(
                "Another editor saved a newer version; refresh before saving"
            ) from exc
        return _public(doc) or {}

    async def restore_version(
        self,
        project_id: str,
        run_id: str | None,
        artifact_name: str,
        version: int,
        actor_id: str,
        *,
        baseline_content: str,
        base_version: int,
        change_summary: str | None = None,
    ) -> dict:
        target = await self.get_version(project_id, run_id, artifact_name, version)
        return await self.create_version(
            project_id,
            run_id,
            artifact_name,
            target["content"],
            actor_id,
            baseline_content=baseline_content,
            base_version=base_version,
            based_on_version=version,
            change_summary=change_summary or f"恢复到 v{version}",
            source="restored",
            restored_from_version=version,
        )

    async def compare_versions(
        self,
        project_id: str,
        run_id: str | None,
        artifact_name: str,
        from_version: int,
        to_version: int,
    ) -> dict:
        older = await self.get_version(
            project_id, run_id, artifact_name, from_version
        )
        newer = await self.get_version(project_id, run_id, artifact_name, to_version)
        diff_lines = list(
            difflib.unified_diff(
                older["content"].splitlines(),
                newer["content"].splitlines(),
                fromfile=f"v{from_version}",
                tofile=f"v{to_version}",
                lineterm="",
            )
        )
        additions = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )
        return {
            "project_id": project_id,
            "run_id": run_id,
            "artifact_name": artifact_name,
            "from_version": from_version,
            "to_version": to_version,
            "additions": additions,
            "deletions": deletions,
            "diff": "\n".join(diff_lines),
        }
