import importlib
import threading
import time
import unittest
from unittest.mock import patch


interrupts = importlib.import_module("util.util")


class InterruptTimeoutTests(unittest.TestCase):
    def tearDown(self):
        interrupts.set_stream_callback(None)
        interrupts.unregister_feedback_slot("project")

    def test_no_activity_auto_skips_after_deadline(self):
        events = []
        interrupts.register_feedback_slot("project")
        interrupts.set_stream_callback(
            lambda project_id, event_type, **payload:
                events.append((event_type, payload))
        )

        with patch.object(interrupts, "INTERRUPT_AUTO_SKIP_SECONDS", 0.01):
            result = interrupts.multiline_input(
                project_id="project",
                interrupt_data={"message": "review"},
            )

        self.assertEqual(result, "no")
        self.assertEqual(events[0][0], "interrupt")
        self.assertEqual(events[0][1]["auto_skip_seconds"], 0.01)
        self.assertEqual(events[-1][0], "interrupt_auto_skipped")

    def test_activity_cancels_auto_skip_and_waits_for_feedback(self):
        interrupt_emitted = threading.Event()
        result = []
        interrupts.register_feedback_slot("project")

        def on_event(project_id, event_type, **payload):
            if event_type == "interrupt":
                interrupt_emitted.set()

        interrupts.set_stream_callback(on_event)
        with (
            patch.object(interrupts, "INTERRUPT_AUTO_SKIP_SECONDS", 0.2),
            patch.object(interrupts, "INTERRUPT_ACTIVE_TIMEOUT_SECONDS", 1),
        ):
            worker = threading.Thread(
                target=lambda: result.append(
                    interrupts.multiline_input(
                        project_id="project",
                        interrupt_data={"message": "review"},
                    )
                )
            )
            worker.start()
            self.assertTrue(interrupt_emitted.wait(timeout=1))
            interrupts.submit_feedback(
                "project", interrupts.HUMAN_ACTIVE_SIGNAL
            )
            time.sleep(0.03)
            interrupts.submit_feedback("project", "approved")
            worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(result, ["approved"])


if __name__ == "__main__":
    unittest.main()
