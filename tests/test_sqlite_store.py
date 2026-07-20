import tempfile
import unittest
from pathlib import Path

from backend.config import settings
from backend.db.mongo import close_db, connect_db, projects_col
from backend.services.artifact_version_service import ArtifactVersionService
from backend.services.event_service import EventService
from backend.services.project_service import ProjectService
from backend.services.run_service import RunQuotaExceeded, RunService


class SQLiteStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_type = settings.DATABASE_TYPE
        self.original_path = settings.SQLITE_PATH
        self.original_quota = settings.PIPELINE_MAX_ACTIVE_PER_USER
        settings.DATABASE_TYPE = "sqlite"
        settings.SQLITE_PATH = str(Path(self.temp_dir.name) / "reagent.db")
        settings.PIPELINE_MAX_ACTIVE_PER_USER = 2
        await connect_db()

    async def asyncTearDown(self):
        await close_db()
        settings.DATABASE_TYPE = self.original_type
        settings.SQLITE_PATH = self.original_path
        settings.PIPELINE_MAX_ACTIVE_PER_USER = self.original_quota
        self.temp_dir.cleanup()

    async def test_project_search_update_and_restart_persistence(self):
        service = ProjectService()
        created = await service.create(
            {
                "user_id": "alice",
                "project_name": "考试系统",
                "description": "支持在线考试",
            }
        )
        await service.create(
            {"user_id": "bob", "project_name": "Other", "description": "private"}
        )
        listed = await service.list_by_user("alice", search="考试")
        self.assertEqual(len(listed["projects"]), 1)
        self.assertEqual(listed["projects"][0]["project_id"], created["project_id"])

        await service.update(created["project_id"], {"description": "新的项目描述"})
        await close_db()
        await connect_db()
        restored = await projects_col().find_one({"project_id": created["project_id"]})
        self.assertEqual(restored["description"], "新的项目描述")

    async def test_run_quota_is_unique_and_terminal_run_releases_slot(self):
        service = RunService()
        project = {"project_id": "p1", "user_id": "alice"}
        first = await service.create(project, {"project_name": "A"})
        second = await service.create(project, {"project_name": "A"})
        with self.assertRaises(RunQuotaExceeded):
            await service.create(project, {"project_name": "A"})

        await service.update_status(first["run_id"], status="completed")
        third = await service.create(project, {"project_name": "A"})
        self.assertNotEqual(second["run_id"], third["run_id"])

    async def test_event_replay_and_artifact_versions(self):
        events = EventService()
        await events.persist(
            {"run_id": "run1", "project_id": "p1", "_seq": 1, "type": "stage_start"}
        )
        await events.persist(
            {"run_id": "run1", "project_id": "p1", "_seq": 2, "type": "completed"}
        )
        replay = await events.list_after("run1", after_event_id=1)
        self.assertEqual([event["_seq"] for event in replay], [2])

        versions = ArtifactVersionService()
        baseline = await versions.latest("p1", "run1", "SRS", "original")
        edited = await versions.create_version(
            "p1",
            "run1",
            "SRS",
            "edited",
            "alice",
            baseline_content="original",
            base_version=baseline["version"],
        )
        history = await versions.list_versions("p1", "run1", "SRS")
        self.assertEqual(edited["version"], 2)
        self.assertEqual([item["version"] for item in history], [2, 1])


if __name__ == "__main__":
    unittest.main()
