import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.artifact_service import ArtifactService
from backend.services.run_service import RunService


class _InsertResult:
    inserted_id = "fake"


class _RunsCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return _InsertResult()

    async def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                doc.update(update["$set"])
                for key in update.get("$unset", {}):
                    doc.pop(key, None)
                break


class RunServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_lifecycle_is_stored_separately_from_project(self):
        collection = _RunsCollection()
        service = RunService()
        project = {"project_id": "p1", "user_id": "alice"}
        config = {"project_name": "Demo", "description": "requirements"}

        with patch(
            "backend.services.run_service.pipeline_runs_col",
            return_value=collection,
        ):
            run = await service.create(project, config)
            await service.update_status(
                run["run_id"], status="running", current_stage="meta_analysis"
            )
            await service.update_status(run["run_id"], status="completed")

        stored = collection.docs[0]
        self.assertEqual(stored["project_id"], "p1")
        self.assertEqual(stored["user_id"], "alice")
        self.assertEqual(stored["status"], "completed")
        self.assertIsNotNone(stored["started_at"])
        self.assertIsNotNone(stored["finished_at"])

    def test_artifacts_are_isolated_by_run_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ArtifactService(output_dir=temp_dir)
            path = service._project_dir("p1", "abc123def456")
            expected = Path(temp_dir) / "p1" / "runs" / "abc123def456"
            self.assertEqual(Path(path), expected)


if __name__ == "__main__":
    unittest.main()
