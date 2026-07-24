import unittest
from unittest.mock import patch

from util import run_with_retry


class _Runner:
    def __init__(self, error=None):
        self.error = error

    def kickoff(self, inputs):
        if self.error:
            raise self.error


class _CrewFactory:
    def __init__(self, error=None):
        self.error = error

    def crew(self):
        return _Runner(self.error)


class RunWithRetryMemoryTests(unittest.TestCase):
    @patch("util._release_crew_memory")
    def test_success_releases_crew_memory(self, release):
        run_with_retry(lambda: _CrewFactory(), {}, "success", retries=1)
        release.assert_called_once_with()

    @patch("util._release_crew_memory")
    def test_failure_releases_memory_after_every_attempt(self, release):
        with self.assertRaisesRegex(Exception, "Failed after 2 retries"):
            run_with_retry(
                lambda: _CrewFactory(RuntimeError("failed")),
                {},
                "failure",
                retries=2,
                delay=0,
            )
        self.assertEqual(release.call_count, 2)


if __name__ == "__main__":
    unittest.main()
