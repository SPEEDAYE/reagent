# External Calls

| Component | External Surface |
|---|---|
| `src/util/llm_config.py` | Builds CrewAI LLM clients from `.env` values. |
| `src/backend/db/mongo.py` | Connects to MongoDB via `MONGODB_URI`. |
| `src/backend/api/routes/*` | Exposes REST and SSE endpoints. |
| `src/backend/services/file_service.py` | Writes uploaded files under `dataset/uploads/<project_id>/`. |
| CrewAI tasks | Call configured LLM provider during artifact generation. |

Secrets are loaded from `.env` and must not be committed.
