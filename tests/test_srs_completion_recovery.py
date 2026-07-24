import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.services import execution


class SrsCompletionRecoveryTests(unittest.TestCase):
    def test_marker_requires_both_artifact_hashes_to_match(self):
        with tempfile.TemporaryDirectory() as output_dir:
            run_dir = (
                Path(output_dir)
                / "project"
                / "runs"
                / "abcdef123456"
            )
            marker_dir = run_dir / ".pipeline"
            marker_dir.mkdir(parents=True)
            files = {
                "SRS.md": b"# complete SRS",
                "SRS.pkl": b"pickle-content",
            }
            for filename, content in files.items():
                (run_dir / filename).write_bytes(content)
            marker = {
                "completed": True,
                "chapter_count": 7,
                "files": {
                    filename: hashlib.sha256(content).hexdigest()
                    for filename, content in files.items()
                },
            }
            (marker_dir / "srs_complete.json").write_text(
                json.dumps(marker),
                encoding="utf-8",
            )

            with patch.object(execution.settings, "OUTPUT_DIR", output_dir):
                verified = execution._srs_completion_marker(
                    "project", "abcdef123456"
                )
                self.assertEqual(verified["chapter_count"], 7)

                (run_dir / "SRS.md").write_text(
                    "# partial or changed", encoding="utf-8"
                )
                self.assertIsNone(
                    execution._srs_completion_marker(
                        "project", "abcdef123456"
                    )
                )


class SrsCompletionReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def test_verified_marker_republishes_terminal_success(self):
        with (
            patch.object(
                execution,
                "_srs_completion_marker",
                return_value={"completed": True},
            ),
            patch.object(
                execution,
                "_update_project_and_run",
                new=AsyncMock(),
            ) as update,
            patch.object(
                execution.stream_manager,
                "publish",
                new=AsyncMock(),
            ) as publish,
        ):
            recovered = await execution._reconcile_completed_srs(
                "project", "abcdef123456"
            )

        self.assertTrue(recovered)
        self.assertEqual(update.await_args.kwargs["status"], "completed")
        event_types = [
            call.args[1]["type"] for call in publish.await_args_list
        ]
        self.assertEqual(
            event_types,
            ["artifact_complete", "stage_complete", "completed", "finished"],
        )


if __name__ == "__main__":
    unittest.main()
