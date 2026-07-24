import os
import tempfile
import unittest
from unittest.mock import patch

# CrewAI initialises its RAG path during import, even though these tests only
# exercise configuration parsing. Keep that import-time path inside a temp dir.
_crewai_storage = tempfile.TemporaryDirectory()
os.environ["CREWAI_STORAGE_DIR"] = _crewai_storage.name
os.environ["LOCALAPPDATA"] = _crewai_storage.name
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

from util import llm_config


class LlmTimeoutConfigTests(unittest.TestCase):
    def test_default_timeout_prevents_unbounded_first_request(self):
        env = {
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "test-model",
            "LLM_API_KEY": "test-key",
        }
        with (
            patch.dict(llm_config.os.environ, env, clear=True),
            patch.object(llm_config, "load_project_env"),
        ):
            config = llm_config.resolve_llm_config()

        self.assertEqual(
            config.timeout,
            llm_config.DEFAULT_LLM_TIMEOUT_SECONDS,
        )

    def test_explicit_timeout_is_preserved(self):
        env = {
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "test-model",
            "LLM_API_KEY": "test-key",
            "LLM_TIMEOUT": "42",
        }
        with (
            patch.dict(llm_config.os.environ, env, clear=True),
            patch.object(llm_config, "load_project_env"),
        ):
            config = llm_config.resolve_llm_config()

        self.assertEqual(config.timeout, 42)


if __name__ == "__main__":
    unittest.main()
