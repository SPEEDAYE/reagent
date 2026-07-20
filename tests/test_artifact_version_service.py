import unittest
from unittest.mock import patch

from backend.db.mongo import DuplicateKeyError
from backend.services.artifact_version_service import (
    ArtifactVersionConflict,
    ArtifactVersionService,
)


class _InsertResult:
    inserted_id = "fake"


class _Cursor:
    def __init__(self, docs, projection=None):
        self.docs = [dict(doc) for doc in docs]
        self.projection = projection or {}
        self.index = 0

    def sort(self, fields, direction=None):
        pairs = fields if isinstance(fields, list) else [(fields, direction)]
        for field, order in reversed(pairs):
            self.docs.sort(key=lambda doc: doc.get(field), reverse=order < 0)
        return self

    def __aiter__(self):
        self.index = 0
        return self

    async def __anext__(self):
        if self.index >= len(self.docs):
            raise StopAsyncIteration
        doc = dict(self.docs[self.index])
        self.index += 1
        for key, included in self.projection.items():
            if included == 0:
                doc.pop(key, None)
        return doc


class _VersionsCollection:
    def __init__(self):
        self.docs = []

    @staticmethod
    def _matches(doc, query):
        return all(doc.get(key) == value for key, value in query.items())

    async def find_one(self, query, projection=None, sort=None):
        matches = [doc for doc in self.docs if self._matches(doc, query)]
        if sort:
            for field, order in reversed(sort):
                matches.sort(key=lambda doc: doc.get(field), reverse=order < 0)
        if not matches:
            return None
        doc = dict(matches[0])
        for key, included in (projection or {}).items():
            if included == 0:
                doc.pop(key, None)
        return doc

    async def insert_one(self, doc):
        identity = (doc["project_id"], doc.get("run_id"), doc["artifact_name"], doc["version"])
        for existing in self.docs:
            current = (
                existing["project_id"], existing.get("run_id"),
                existing["artifact_name"], existing["version"],
            )
            if current == identity:
                raise DuplicateKeyError("duplicate")
        self.docs.append(dict(doc))
        return _InsertResult()

    def find(self, query, projection=None):
        return _Cursor(
            [doc for doc in self.docs if self._matches(doc, query)], projection
        )


class ArtifactVersionServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.collection = _VersionsCollection()
        self.service = ArtifactVersionService()
        self.patch = patch(
            "backend.services.artifact_version_service.artifact_versions_col",
            return_value=self.collection,
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    async def test_generated_baseline_and_edits_are_immutable(self):
        baseline = await self.service.latest("p1", "run1", "SRS", "original")
        edited = await self.service.create_version(
            "p1", "run1", "SRS", "edited", "alice",
            baseline_content="original", base_version=1, change_summary="完善范围",
        )

        self.assertEqual(baseline["version"], 1)
        self.assertEqual(edited["version"], 2)
        self.assertEqual(self.collection.docs[0]["content"], "original")
        self.assertEqual(self.collection.docs[1]["content"], "edited")

    async def test_stale_editor_is_rejected(self):
        await self.service.latest("p1", "run1", "SRS", "original")
        await self.service.create_version(
            "p1", "run1", "SRS", "alice edit", "alice",
            baseline_content="original", base_version=1,
        )
        with self.assertRaises(ArtifactVersionConflict):
            await self.service.create_version(
                "p1", "run1", "SRS", "stale edit", "bob",
                baseline_content="original", base_version=1,
            )

    async def test_restore_creates_new_version_and_compare_returns_diff(self):
        await self.service.latest("p1", "run1", "SRS", "line one\nline two")
        await self.service.create_version(
            "p1", "run1", "SRS", "line one\nline changed", "alice",
            baseline_content="line one\nline two", base_version=1,
        )
        restored = await self.service.restore_version(
            "p1", "run1", "SRS", 1, "alice",
            baseline_content="line one\nline two", base_version=2,
        )
        diff = await self.service.compare_versions("p1", "run1", "SRS", 1, 2)

        self.assertEqual(restored["version"], 3)
        self.assertEqual(restored["source"], "restored")
        self.assertEqual(restored["restored_from_version"], 1)
        self.assertEqual(diff["additions"], 1)
        self.assertEqual(diff["deletions"], 1)

    async def test_versions_are_isolated_by_run(self):
        await self.service.latest("p1", "run1", "SRS", "first run")
        await self.service.latest("p1", "run2", "SRS", "second run")

        run1 = await self.service.list_versions("p1", "run1", "SRS")
        run2 = await self.service.list_versions("p1", "run2", "SRS")
        self.assertEqual(run1[0]["content_hash"], self.collection.docs[0]["content_hash"])
        self.assertEqual(run2[0]["content_hash"], self.collection.docs[1]["content_hash"])
        self.assertNotEqual(run1[0]["content_hash"], run2[0]["content_hash"])


if __name__ == "__main__":
    unittest.main()
