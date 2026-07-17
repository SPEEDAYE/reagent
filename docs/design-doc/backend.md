# Backend Design — FastAPI + CrewAI Bridge

> Scope: [../../backend/](../../src/backend/). Covers HTTP/SSE layer, MongoDB access, per-project execution orchestration.

## 1. Bootstrap

[../../backend/main.py](../../src/backend/main.py) is the FastAPI app factory:

| Line | Responsibility |
|------|----------------|
| 10–14 | Instantiate `FastAPI(title="REagent API", version="1.0.0")` |
| 16–22 | CORS middleware (`allow_origins = settings.CORS_ORIGINS = ["*"]`) |
| 25–28 | `@app.on_event("startup")` → `connect_db()` + `stream_manager.set_loop(asyncio.get_event_loop())` — **critical**: captures the main event loop so worker threads can schedule coroutines onto it |
| 31–33 | `@app.on_event("shutdown")` → `close_db()` |
| 36 | `register_routes(app)` — mounts all route modules |

Configuration lives in [../../backend/config.py](../../src/backend/config.py): loads `.env` from project root with a fallback one level up; exposes `Settings` singleton (`MONGODB_URI`, `DB_NAME`, `CORS_ORIGINS`, `PROJECT_ROOT`, `OUTPUT_DIR`, `UPLOAD_DIR`).

## 2. Routes

Registered via [../../backend/api/routes/\_\_init\_\_.py](../../src/backend/api/routes/__init__.py). 12 endpoints across 5 router files:

| File | Endpoints |
|------|-----------|
| [health.py](../../src/backend/api/routes/health.py) | `GET /health` — returns `{status, db_connected, timestamp}` |
| [project.py](../../src/backend/api/routes/project.py) | `POST /project/create`, `GET /project/list/{user_id}`, `GET /project/{pid}`, `DELETE /project/{pid}` |
| [stream.py](../../src/backend/api/routes/stream.py) | `POST /graph/stream/create`, `POST /graph/stream/resume`, `GET /graph/stream/{pid}` (SSE) |
| [artifacts.py](../../src/backend/api/routes/artifacts.py) | `GET /artifacts/{pid}`, `GET /artifacts/{pid}/{name}`, `POST /artifacts/export_pdf` |
| [files.py](../../src/backend/api/routes/files.py) | `POST /files/upload` (multipart) |

Request/response DTOs: [../../backend/models/requests.py](../../src/backend/models/requests.py), [../../backend/models/responses.py](../../src/backend/models/responses.py).

## 3. Services

### 3.1 StreamManager — [../../backend/services/stream_manager.py](../../src/backend/services/stream_manager.py)

Singleton (`stream_manager` at module bottom) managing per-project SSE event queues.

| Method | Role |
|--------|------|
| `set_loop(loop)` | Store main event loop (called at startup) |
| `create_queue(pid)` / `remove_queue(pid)` | Queue lifecycle |
| `publish(pid, event)` (async) | Append event to queue from async context |
| `publish_sync(pid, event)` | **Sync-safe**: `asyncio.run_coroutine_threadsafe(publish(...), self._loop)` — called from worker thread |
| `subscribe(pid)` (async generator) | Yields `{"event": type, "data": json}` frames; closes on `finished` or non-recoverable `error` |

Auto-prepends `timestamp` (UTC ISO) if missing. Emits an initial `connected` frame before the loop.

### 3.2 ExecutionService — [../../backend/services/execution.py](../../src/backend/services/execution.py)

Core orchestrator. Key structure:

```python
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reagent")  # L15
_active: dict[str, Future] = {}                                                # L16
```

`ExecutionService.start(pid, config)` (L52–76):
1. Check not already active (L53).
2. `register_feedback_slot(pid)` + `set_stream_callback(_emit)` from `util.util` (L57–59).
3. `stream_manager.create_queue(pid)` (L62).
4. Re-capture event loop (L65).
5. Update project status → `running`, `current_stage="meta_analysis"` (L69).
6. Submit `_run_pipeline(pid, config)` to the executor; store future in `_active` (L73–76).

`ExecutionService.resume(pid, resume_type, human_comment)` (L78–91):
- Maps `resume_type` → feedback value sent into worker via `submit_feedback`:
  - `"accept"` → `"no"` (pipeline continues)
  - `"feedback"` → `human_comment` (triggers `modify_agent`)
  - `"redo_artifact"` → `human_comment` or `"redo"`
  - `"skip"` → `"exit"`

`_run_pipeline(pid, config)` (L98–307): runs in a worker thread.
- Sets `sys.path`, `cwd`, loads `.env` (L103–114).
- `set_store_path(f"experiment/{pid}")` (L119–121) — **must be relative** because CrewAI concatenates cwd.
- Sets `CREWAI_STORAGE_DIR = crewai_storage/{pid}` (L124–126).
- **Monkey-patches `util.run_with_retry`** (L132–159) to wrap each crew call with:
  - `_update_project_status_sync` (current_crew)
  - `_emit("crew_start")` before
  - `_emit("artifact_complete")` on success
  - `_emit("error", recoverable=True)` on failure
- Iterates 6 phases (L167–285): MetaAnalysis → BRDev → Elicitation → Analysis → NonStandard → SRS. Each phase emits `stage_start` + `stage_complete`.
- On exception: emit non-recoverable `error` (L296–303).
- `finally`: pop `_active`, **restore original `run_with_retry`** (L304–307).

⚠️ The patched `run_with_retry` is assigned to `util_mod.run_with_retry`. Pipeline modules import `run_with_retry` by name (`from util import run_with_retry`), which binds at import time. Ensure imports happen after the monkey-patch — verified in [../../backend/services/execution.py:129](../../src/backend/services/execution.py#L129) where `from util import run_with_retry` is executed before patching, but patching rewrites the module attribute. Subsequent imports inside the worker pick up the new attribute via `util_mod.run_with_retry` resolution.

### 3.3 ProjectService — [../../backend/services/project_service.py](../../src/backend/services/project_service.py)

Async MongoDB CRUD on the `projects` collection. `create()`, `update_status()`, `list_by_user()`, `get()`, `delete()` (also cleans artifacts + uploaded files).

### 3.4 ArtifactService — [../../backend/services/artifact_service.py](../../src/backend/services/artifact_service.py)

- Maintains a registry of 17 artifacts + filename mapping.
- `list(pid)`: scans `experiment/{pid}/*.md`, joins with [../../util/DAG.py](../../src/util/DAG.py) `Artifact_Dependance_rules` for dependencies/dependents.
- `get_content(pid, name)`: returns markdown.
- `export_pdf(pid, name)`: uses `reportlab` to render markdown (basic — no Mermaid rendering).

### 3.5 FileService — [../../backend/services/file_service.py](../../src/backend/services/file_service.py)

Multipart upload to `dataset/uploads/{pid}/`; record stored in `uploaded_files` collection.

## 4. Data Models

Mongo collections:

```
projects:
  _id: str (UUID/project_id)
  user_id: str
  project_name: str
  description: str
  srs_template: str | None   # "IEEE" | "Initial" | None (user-uploaded example)
  status: "created" | "running" | "interrupted" | "finished" | "error"
  current_stage: str | None
  current_crew: str | None
  created_at / updated_at: ISO datetime

uploaded_files:
  _id: str
  project_id: str
  file_type: "data" | "srs_template"
  filename: str
  path: str
  size_bytes: int
  uploaded_at: ISO datetime
```

## 5. Request Lifecycles (representative)

### POST `/graph/stream/create`
1. Pydantic validates `{project_id, user_id, human_request?}`.
2. Handler fetches project from Mongo; builds `config` dict.
3. `ExecutionService.start(pid, config)` → queue + callback + worker dispatch.
4. Returns `{status: "started"}` immediately.

### GET `/graph/stream/{pid}` (SSE)
1. Handler returns `EventSourceResponse(stream_manager.subscribe(pid))`.
2. The async generator yields `connected`, then forwards events from the queue.
3. Closes when a `finished` or non-recoverable `error` event arrives.

### POST `/graph/stream/resume`
1. Pydantic validates `{project_id, resume_type, human_comment?}`.
2. `ExecutionService.resume` maps type and calls `submit_feedback(pid, value)`.
3. The worker's `multiline_input` unblocks and returns the value.
4. Handler returns `{status: "resumed"}`.

## 6. Cross-Cutting Concerns

| Concern | Notes |
|---------|-------|
| **Thread safety** | Path state: thread-local + global fallback ([../../util/util.py:12](../../src/util/util.py#L12)). MongoDB: single async motor client, safe under asyncio. |
| **Error recovery** | Crew-level: `run_with_retry` retries 5× with 15s delay. Stage-level: exceptions bubble up to `_run_pipeline` which marks project `error` and stops. |
| **Observability** | Print statements only; no structured logging. `reagent-api.log` captures stdout. |
| **Auth** | None. All endpoints open. Assumes intranet / SSH tunnel deployment. |

## 7. Known Issues (backend)

- ⚠️ `_active` is never cleaned for crashed worker processes (only via `finally` — survives normal completion and exceptions, but not hard kills).
- ⚠️ `stream_manager.remove_queue` is never called — queues accumulate for the life of the process.
- ⚠️ CORS is `*` — fine for dev; must be restricted for prod.
- ⚠️ Interrupt timeout: `slot["event"].wait()` has no timeout, so a disconnected frontend leaves the worker blocked until the process is killed.
