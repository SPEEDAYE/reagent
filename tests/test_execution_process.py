import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from backend.services import execution


def _crash_worker(project_id, config, event_queue, feedback_queue, cancel_event):
    os._exit(7)


class ProcessExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await execution.shutdown_execution_runtime()
        execution._active.clear()
        execution._ipc.clear()
        execution._project_runs.clear()

    async def test_two_projects_use_isolated_workers_and_feedback_channels(self):
        service = execution.ExecutionService(execution._ipc_test_pipeline)
        with (
            patch.object(execution.project_svc, "update_status", new=AsyncMock()),
            patch.object(execution.run_svc, "update_status", new=AsyncMock()),
            patch(
                "backend.services.stream_manager.event_svc.persist",
                new=AsyncMock(),
            ),
        ):
            await service.start("p1", {"project_name": "one"}, "aaa111bbb222")
            await service.start("p2", {"project_name": "two"}, "ccc333ddd444")
            pump1 = execution._ipc["p1"]["pump_task"]
            pump2 = execution._ipc["p2"]["pump_task"]

            for _ in range(50):
                h1 = list(execution.stream_manager._history.get("p1", []))
                h2 = list(execution.stream_manager._history.get("p2", []))
                if any(e.get("type") == "stage_start" for e in h1) and any(
                    e.get("type") == "stage_start" for e in h2
                ):
                    break
                await asyncio.sleep(0.05)

            await service.resume("p1", "feedback", "feedback-one")
            await service.resume("p2", "feedback", "feedback-two")
            await asyncio.wait_for(asyncio.gather(pump1, pump2), timeout=15)

        history1 = list(execution.stream_manager._history["p1"])
        history2 = list(execution.stream_manager._history["p2"])
        start1 = next(e for e in history1 if e.get("type") == "stage_start")
        start2 = next(e for e in history2 if e.get("type") == "stage_start")
        feedback1 = next(e for e in history1 if e.get("type") == "feedback_received")
        feedback2 = next(e for e in history2 if e.get("type") == "feedback_received")

        self.assertNotEqual(start1["worker_pid"], start2["worker_pid"])
        self.assertEqual(feedback1["feedback"], "feedback-one")
        self.assertEqual(feedback2["feedback"], "feedback-two")
        self.assertEqual(feedback1["run_id"], "aaa111bbb222")
        self.assertEqual(feedback2["run_id"], "ccc333ddd444")

    async def test_worker_crash_resets_pool_for_next_pipeline(self):
        crashing_service = execution.ExecutionService(_crash_worker)
        healthy_service = execution.ExecutionService(execution._ipc_test_pipeline)
        with (
            patch.object(execution.project_svc, "update_status", new=AsyncMock()),
            patch.object(execution.run_svc, "update_status", new=AsyncMock()),
            patch(
                "backend.services.stream_manager.event_svc.persist",
                new=AsyncMock(),
            ),
        ):
            await crashing_service.start(
                "crash-project", {"project_name": "crash"}, "aaa111bbb222"
            )
            crash_pump = execution._ipc["crash-project"]["pump_task"]
            await asyncio.wait_for(crash_pump, timeout=15)

            crash_history = list(
                execution.stream_manager._history["crash-project"]
            )
            crash_error = next(
                event for event in crash_history if event.get("type") == "error"
            )
            self.assertIn("process pool was reset automatically", crash_error["error"])

            await healthy_service.start(
                "healthy-project", {"project_name": "healthy"}, "ccc333ddd444"
            )
            healthy_pump = execution._ipc["healthy-project"]["pump_task"]

            for _ in range(100):
                history = list(
                    execution.stream_manager._history.get("healthy-project", [])
                )
                if any(event.get("type") == "stage_start" for event in history):
                    break
                await asyncio.sleep(0.05)

            await healthy_service.resume("healthy-project", "accept")
            await asyncio.wait_for(healthy_pump, timeout=15)

        healthy_history = list(
            execution.stream_manager._history["healthy-project"]
        )
        self.assertTrue(
            any(event.get("type") == "completed" for event in healthy_history)
        )


if __name__ == "__main__":
    unittest.main()
