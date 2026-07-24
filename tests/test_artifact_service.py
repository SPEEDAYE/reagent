import os
import tempfile
import unittest

from backend.services.artifact_service import ArtifactService


class ArtifactServiceWriteTests(unittest.TestCase):
    def test_write_content_updates_selected_run_artifact_atomically(self):
        with tempfile.TemporaryDirectory() as output_dir:
            service = ArtifactService(output_dir=output_dir)

            path = service.write_content(
                "project-1",
                "business_scope",
                "# 人工修改后的业务范围",
                "abcdef123456",
            )

            self.assertTrue(os.path.isfile(path))
            artifact = service.get_content(
                "project-1", "business_scope", "abcdef123456"
            )
            self.assertEqual(artifact["content"], "# 人工修改后的业务范围")
            self.assertEqual(artifact["status"], "completed")

    def test_write_content_rejects_unknown_artifact(self):
        with tempfile.TemporaryDirectory() as output_dir:
            service = ArtifactService(output_dir=output_dir)

            with self.assertRaisesRegex(ValueError, "Unknown artifact"):
                service.write_content("project-1", "../outside", "content")


if __name__ == "__main__":
    unittest.main()
