import unittest
from unittest.mock import AsyncMock, patch

from backend.services.stream_manager import StreamManager


class StreamPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_run_resets_project_event_sequence(self):
        manager = StreamManager()
        manager.create_queue("p1", run_id="run-one")
        with patch(
            "backend.services.stream_manager.event_svc.persist",
            new=AsyncMock(),
        ):
            first = {"type": "stage_start", "run_id": "run-one"}
            await manager.publish("p1", first)
            manager.create_queue("p1", run_id="run-two")
            second = {"type": "stage_start", "run_id": "run-two"}
            await manager.publish("p1", second)

        self.assertEqual(first["_seq"], 1)
        self.assertEqual(second["_seq"], 1)
        self.assertEqual(len(manager._history["p1"]), 1)

    async def test_persist_failure_does_not_break_live_delivery(self):
        manager = StreamManager()
        manager.create_queue("p1", run_id="run-one")
        with patch(
            "backend.services.stream_manager.event_svc.persist",
            new=AsyncMock(side_effect=RuntimeError("db unavailable")),
        ):
            event = {"type": "stage_start", "run_id": "run-one"}
            await manager.publish("p1", event)

        delivered = await manager._queues["p1"].get()
        self.assertEqual(delivered["type"], "stage_start")


if __name__ == "__main__":
    unittest.main()
