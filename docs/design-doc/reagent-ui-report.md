# REagent 1.0 UI — Comprehensive Understanding Report

_Generated: 2026-04-12. Sources: README.md, source tree inspection, sub-agent analysis of 40+ files._

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Functional Flow](#2-functional-flow)
3. [Core Data Structures](#3-core-data-structures)
4. [Module Dependencies](#4-module-dependencies)
5. [Configuration & External Dependencies](#5-configuration--external-dependencies)
6. [Issues & Findings](#6-issues--findings)
7. [Navigation Index](#7-navigation-index)

---

## 1. Project Overview

**Position**: REagent 1.0 is an AI-powered Requirements-Engineering automation platform. It takes a free-form project description plus (optionally) a sample SRS document and produces 17 Requirements-Engineering artifacts, culminating in a full IEEE-style Software Requirements Specification.

**Two runtime modes**:

| Mode | Entry | Use case |
|------|-------|----------|
| CLI | [src/reagent/main.py](src/reagent/main.py) + [start.sh](start.sh) | Batch / single-project debug |
| API | [backend/main.py](src/backend/main.py) (FastAPI on :8000) | Web UI with SSE + interrupt/resume |

**Tech stack**: CrewAI 1.6.x (multi-agent LLM orchestration), FastAPI, Uvicorn, MongoDB (motor async), sse-starlette, Pydantic v2, pdfplumber / python-docx / PyPDF2, reportlab, ChromaDB/LanceDB.

**Deployment target**: Ubuntu server at `se.aiseclab.cn:10122`, path `/home/carl/reagent/`, nginx on :9998 reverse-proxying :8000. See [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md).

**What makes it non-trivial**:
- The 17 artifacts have a non-trivial dependency graph — feedback requires downstream regeneration via a DAG-aware `modify_agent`.
- 3 interrupt gates require async↔sync thread coordination (FastAPI async loop ↔ CrewAI sync worker).
- LLM calls are slow (20–40 min end-to-end), making streaming progress and resumability essential.

---

## 2. Functional Flow

### 2.1 High-Level Pipeline

```
Description.txt
    │
    ▼
[1] MetaAnalysis ─── produces template, skeleton, content-plan,
                     chapter-dependence, artifact-planning (cached in dataset/template-cache/)
    │
    ▼
[2] BusinessRequirements ★ survey → context_diagram → event_list →
                     user_introduction → feature_tree → business_scope [INTERRUPT]
                     → BRD (chapter-by-chapter) [INTERRUPT]
    │
    ▼
[3] RequirementElicitation ★ use_case + non_functional_requirements [INTERRUPT]
    │
    ▼
[4] RequirementAnalysis (DAG-ordered) ─── data_dictionary, ERD, DFD,
                                           functional_requirements, dialog_map
    │
    ▼
[5] NonStandardProcess ─── usage_scenario, state_transition_diagram
    │
    ▼
[6] SRS Generation ─── SRSplaningCrew + SRSev, chapter-by-chapter in topo order
    │
    ▼
SRS.md  +  BRD.md  +  15 supporting artifacts   (in experiment/{project_id}/)
```

### 2.2 Stage Responsibilities & Function Anchors

| # | Stage | Entry | File:Line |
|---|-------|-------|-----------|
| 1 | MetaAnalysis | `MetaAnalysisrun` | [src/reagent/StandardProcess.py:48](src/reagent/StandardProcess.py#L48) |
| 2 | BusinessRequirements | `BRDevrun` | [src/reagent/StandardProcess.py:135](src/reagent/StandardProcess.py#L135) |
| 3 | RequirementElicitation | `RequirementElicitationrun` | [src/reagent/StandardProcess.py:235](src/reagent/StandardProcess.py#L235) |
| 4 | RequirementAnalysis | `RequirementAnalysisrun` | [src/reagent/StandardProcess.py:277](src/reagent/StandardProcess.py#L277) |
| 5 | NonStandardProcess | `NonStandardProcessrun` | [src/reagent/NonStandardProcess.py](src/reagent/NonStandardProcess.py) |
| 6 | SRS Generation | `RequirementSpecificationrun` | [src/reagent/main.py:24](src/reagent/main.py#L24) |

### 2.3 API Request Lifecycle (web mode)

1. **`POST /project/create`** → [backend/api/routes/project.py](src/backend/api/routes/project.py) → `ProjectService.create` inserts into `projects` collection; returns `project_id`.
2. **`POST /graph/stream/create`** → [backend/api/routes/stream.py](src/backend/api/routes/stream.py) → `ExecutionService.start` (which registers feedback slot, creates SSE queue, submits `_run_pipeline` to `ThreadPoolExecutor`).
3. **`GET /graph/stream/{pid}`** → subscribes to the asyncio.Queue; emits SSE frames (`connected → stage_start → crew_start → artifact_complete → interrupt → stage_complete → finished`).
4. **`POST /graph/stream/resume`** → [backend/services/execution.py:78](src/backend/services/execution.py#L78) → maps `resume_type` to a string (`"no"`/`"exit"`/human_comment) and calls `submit_feedback(pid, value)` which sets a `threading.Event`, unblocking `multiline_input` in the worker.
5. **`GET /artifacts/{pid}`** / **`GET /artifacts/{pid}/{name}`** → [backend/services/artifact_service.py](src/backend/services/artifact_service.py) scans `experiment/{pid}/` and joins with the DAG rules.

### 2.4 Interrupt / Feedback Loop

Worker side ([util/util.py:80](src/util/util.py#L80) `multiline_input`):
```python
if project_id:          # API mode
    _stream_callback(pid, {"type": "interrupt", "interrupt_type": ..., ...})
    slot["event"].wait()        # blocks worker thread
    return slot["value"]
```

Async side:
```python
POST /resume → ExecutionService.resume
    → submit_feedback(pid, mapped_value)
        → slot["value"] = mapped_value; slot["event"].set()
```

Then [StandardProcess.py:176–182](src/reagent/StandardProcess.py#L176):
```python
if answer.lower() != "no":
    feedback_list.append(answer)
    execute = modify_agent(feedback_list, project_name, Description)  # → re-run affected artifacts
    continue
```

`modify_agent` ([StandardProcess.py:6](src/reagent/StandardProcess.py#L6)):
1. `BRDModifyLocateCrew` — decides *which* artifacts to regenerate (writes `BRD_modify.md`, JSON list).
2. `get_dependent_artifacts(re_execute) & set(reference)` — BFS over [util/DAG.py:23](src/util/DAG.py#L23) to include transitive downstream.
3. `BRDModifyCrew` — regenerates those artifacts with feedback injected.

### 2.5 SRS Chapter-by-Chapter Generation

[src/reagent/main.py:24–72](src/reagent/main.py#L24):
```python
chapter_sequence = topological_sort(chapter_dependence)
SRS = parse_skeleton_to_document_template(document_skeleton, authors='csl-gpt4.1')
SRS_example = split_markdown_by_h2(read_markdown(srs_example_path))

for i, chapter in enumerate(chapter_sequence):
    SRSplaningCrew.kickoff({SRS_example[i+1], reference (metadata), dep_chapter_content})
    prompt = get_SRS_planning()
    SRSev.kickoff({SRS_initial_template.SUBCHAPTERS[i], reference (w/ content),
                   chapter_reference (prior dep chapters), prompt, chapter_index})
    # post_process(): parse chapter JSON → SRS.write_file(chapter) → pickle + write SRS.md
```

---

## 3. Core Data Structures

### 3.1 MongoDB Collections

| Collection | Primary key | Fields |
|------------|-------------|--------|
| `projects` | `_id` (project_id/UUID) | user_id, project_name, description, srs_template, status, current_stage, current_crew, timestamps |
| `uploaded_files` | `_id` | project_id, file_type (data\|srs_template), filename, path, size_bytes, uploaded_at |

Status transitions: `created → running ↔ interrupted → finished | error`.

### 3.2 In-Process Data

| Structure | Where | Purpose |
|-----------|-------|---------|
| `_thread_local.store_path` | [util/util.py:12](src/util/util.py#L12) | Per-project output dir (`experiment/{pid}`) |
| `_feedback_registry[pid] = {event, value}` | [util/util.py:50](src/util/util.py#L50) | Threading.Event slots for interrupt blocking |
| `_stream_callback` | [util/util.py:51](src/util/util.py#L51) | Injected by backend to emit SSE `interrupt` events |
| `_executor`, `_active` | [backend/services/execution.py:15–16](src/backend/services/execution.py#L15) | Single worker; map of running futures |
| `stream_manager._queues[pid]` | [backend/services/stream_manager.py:14](src/backend/services/stream_manager.py#L14) | `asyncio.Queue` per project |

### 3.3 Document Model

```
Document (root)
├── TITLE, INTRODUCTION, AUTHOR, SUBCHAPTERS
└── SUBCHAPTERS: list[CHAPTER]
    ├── TITLE, SECTION (e.g. "1.2"), INTRODUCTION
    ├── Structure: list[dict]   ← actual content
    ├── TIMESTAMP: list[datetime]
    ├── WRITTEN: bool           ← for only_show_written rendering
    └── SUBCHAPTERS: list[CHAPTER]  ← recursive (up to 4 levels)
```

Classes: [src/util/doc_template/chapter.py](src/util/doc_template/chapter.py), [src/util/doc_template/document.py](src/util/doc_template/document.py).

Subclasses: `BusinessRequirement`, `SoftwareRequirementSpecification` (marker subclasses for type-based dispatch in template factories).

Rendering: `Document.get_whole_document()` walks CHAPTER tree, emits markdown with heading level `= len(SECTION.split('.'))`.

### 3.4 Template Cache Entry

A pickle at `dataset/template-cache/document_template_{sha256}.pkl` holds:
```python
(document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing)
```

Hash key: SHA-256 of `read_markdown(doc_example_path)` (or of a filename string for the `IEEE`/`Initial` branches).

### 3.5 Artifact Dependency Rules

[util/DAG.py:4](src/util/DAG.py#L4) `Artifact_Dependance_rules` is the canonical dict mapping each artifact to its direct dependencies. All DAG ops (topological sort, impact propagation, cycle detection) derive from this.

---

## 4. Module Dependencies

### 4.1 Import Map (simplified)

```
backend/main.py
  → backend.api.routes (register_routes)
  → backend.db.mongo (connect_db)
  → backend.services.stream_manager
  → backend.config.settings

backend/services/execution.py
  → backend.services.stream_manager
  → backend.services.project_service
  (at runtime, from worker thread:)
  → util.util (set_store_path, register_feedback_slot, set_stream_callback)
  → util (run_with_retry — monkey-patched inside _run_pipeline)
  → StandardProcess (Meta/BRDev/Elicitation/Analysis)
  → NonStandardProcess
  → main (RequirementSpecificationrun)

src/reagent/main.py
  → util.*
  → StandardProcess, NonStandardProcess
  → RequirementExtraction (only if --data_path provided)
  → RequirementSpecification (deferred import)

src/reagent/StandardProcess.py
  → util.*
  → BusinessRequirements (wildcard)
  → RequirementAnalysis crews (lazy)
  → MetaAnalysis crews (lazy)

src/reagent/*.py (crews)
  → util.SoftwareManager (base class)
  → util (helpers)
  → src/reagent/config/*.yaml (agent + task definitions)

util/*.py
  → util.llm_config → crewai.LLM
  → util.DAG (no external)
  → util.doc_template (no external)
```

### 4.2 Circular-Risk Points

- `util/__init__.py` uses `from util.util import *` etc. — acceptable since submodules don't import from `util/__init__.py`.
- `execution.py` does lazy imports of pipeline modules *inside* `_run_pipeline` to ensure the worker thread runs after `set_store_path` and env setup.

### 4.3 Runtime Sequence

```
startup → register_routes
        → connect_db
        → stream_manager.set_loop(event_loop)

POST /graph/stream/create
  → ExecutionService.start
    → register_feedback_slot(pid)
    → set_stream_callback(_emit)
    → stream_manager.create_queue(pid)
    → update_status('running')
    → loop.run_in_executor(_executor, _run_pipeline, pid, config)
                                   ↓
                     Worker thread: set_store_path, monkey-patch run_with_retry
                     → import StandardProcess (lazy), call each stage
                     → each crew kickoff emits crew_start / artifact_complete via _emit
                     → at interrupt, multiline_input blocks on threading.Event
                     → finally: restore run_with_retry, pop _active
```

---

## 5. Configuration & External Dependencies

### 5.1 Environment Variables (.env)

| Var | Consumer | Purpose |
|-----|----------|---------|
| `OPENAI_KEY` / `OPENAI_API_KEY` | [util/llm_config.py](src/util/llm_config.py) | LLM auth |
| `OPENAI_MODEL` / `LLM_MODEL` | same | Model name |
| `OPENAI_BASE_URL` | same | Required for non-OpenAI providers |
| `LLM_PROVIDER` / `MODEL_PROVIDER` | same | Pick provider (openai/deepseek/qwen/ucloud/zhiyuan) |
| `MONGODB_URI` | [backend/config.py:17](src/backend/config.py#L17) | Mongo connection |
| `DB_NAME` | same | Default `reagent` |
| `CREWAI_STORAGE_DIR` | [execution.py:126](src/backend/services/execution.py#L126) | Per-project CrewAI storage |

.env loading: [util/llm_config.py:27](src/util/llm_config.py#L27) loads `WORKSPACE_ROOT/.env` then `PROJECT_ROOT/.env` (override=True). Workspace .env is at `/home/chunkit/VScode_project/.env` per user preference.

### 5.2 Python Dependencies (key)

| Category | Package | Version |
|----------|---------|---------|
| Agent framework | `crewai[tools]` | 1.6.0 |
| Web | `fastapi` | 0.135.2 |
| Web server | `uvicorn[standard]` | 0.38.0 – 0.42.0 |
| SSE | `sse-starlette` | 3.0.3 – 3.3.4 |
| DB | `motor` (async Mongo) | 3.7.1 |
| LLM | `openai` | 2.8.1 |
| Validation | `pydantic` | 2.12.4 |
| PDF parsing | `pdfplumber`, `pdfminer.six`, `PyPDF2`, `python-docx` | — |
| PDF export | `reportlab` | — |
| Vector stores | `chromadb`, `lancedb` | 1.1.1 / 0.25.3 |
| .env | `python-dotenv` | 1.2.x |
| Multipart | `python-multipart` | 0.0.20 – 0.0.22 |

Dev vs prod: [requirements.txt](requirements.txt) (dev pinned) vs [requirements_deploy.txt](requirements_deploy.txt) (older Ubuntu-compatible).

### 5.3 External Services

| Service | Access | Purpose |
|---------|--------|---------|
| LLM provider | HTTPS (OpenAI-compatible) | All crew tasks |
| MongoDB | `localhost:27017` | Project + file metadata |
| (optional) LandingAI ADE | via `RequirementExtraction.py` | PDF/Office parsing when `--data_path` given |

### 5.4 Configuration Files

| File | Role |
|------|------|
| [src/config/agent/agents.yaml](src/config/agent/agents.yaml) | Agent role/goal/backstory definitions |
| [src/config/task/tasks.yaml](src/config/task/tasks.yaml) | Task prompts (Chinese, 26 tasks) |
| [src/config/task/tasks_eng.yaml](src/config/task/tasks_eng.yaml) | Task prompts (English, parallel file) |
| [pyproject.toml](pyproject.toml) | Package metadata + CLI entry points (`reagent`, `run_crew`, `train`, `replay`, `test`) |
| [backend/config.py](src/backend/config.py) | Settings singleton |

---

## 6. Issues & Findings

### 6.1 Inconsistencies

✅ **[CRITICAL — FIXED 2026-04-12]** Missing symbol `build_optional_tools`. [src/reagent/BusinessRequirements.py:27](src/reagent/BusinessRequirements.py#L27) imports `build_optional_tools` from `util.SoftwareManager`. The function was not defined and every pipeline start (API and CLI) raised `ImportError` on Stage-2 import, which — combined with the "silent reconnect" issue below — presented as a pipeline hung in `pending` state. Fix: added `build_optional_tools()` to [util/SoftwareManager.py](src/util/SoftwareManager.py) returning `[]` by default; opts in to `WebsiteSearchTool` when `ENABLE_WEBSITE_SEARCH_TOOL=1`. See [docs/exec-doc/2026-04-12-fix-pipeline-hang.md](docs/exec-doc/2026-04-12-fix-pipeline-hang.md).

✅ **[High — FIXED 2026-04-12]** Silent SSE pings after terminal state. When a pipeline finishes or errors, the async queue stays alive; later reconnects hang on `queue.get()` while sse-starlette emits 15-second keep-alive pings — exactly what the debugger observed. Fix: [backend/api/routes/stream.py](src/backend/api/routes/stream.py) now checks project status at subscribe time and emits a synthetic replay frame (with `last_error` / `finished`) before closing. [backend/services/execution.py](src/backend/services/execution.py) persists `last_error` on the project document.

✅ **[High — FIXED 2026-04-12]** Duplicate outer loop in `NonStandardProcessrun` ([src/reagent/NonStandardProcess.py](src/reagent/NonStandardProcess.py)): removed the redundant outer loop so each artifact runs exactly once in topological order.

⚠️ **[High] CLI mode skips BRDev** — [src/reagent/StandardProcess.py:292–296](src/reagent/StandardProcess.py#L292) `StandardProcessrun` calls only `MetaAnalysisrun → RequirementElicitationrun → RequirementAnalysisrun`. It does **not** call `BRDevrun`. The API path in [backend/services/execution.py:199](src/backend/services/execution.py#L199) calls it explicitly. CLI users running [start.sh](start.sh) therefore get no BRD, survey, feature_tree, context_diagram, event_list, user_introduction, or business_scope.

⚠️ **[Medium] `StandardProcessrun` argument ignored** — it accepts `SRS_template` but the deeper `RequirementElicitationrun` and `RequirementAnalysisrun` receive no project_id, so CLI mode cannot use API-style interrupts (which is expected; just note the branching).

⚠️ **[Medium] Task YAML duplication** — [tasks.yaml](src/config/task/tasks.yaml) (Chinese) and [tasks_eng.yaml](src/config/task/tasks_eng.yaml) are parallel. Only Chinese is used; English is stale unless explicitly loaded.

### 6.2 Dead / Latent-Bug Code

⚠️ **[High] `paragraph` class broken getters** — [src/util/doc_template/chapter.py:34–46](src/util/doc_template/chapter.py#L34) `get_last_content`, `get_all_content` (base), `get_references` reference non-existent `self.CONTENT` / `self.REFERENCE`. Calling them raises `AttributeError`. Appears unused — safe to delete.

⚠️ **[Medium] Commented-out `get_reference` v1** — [util/__init__.py:65–106](src/util/__init__.py#L65) large block of dead code from a prior implementation.

⚠️ **[Medium] Unused `justfordebug()`** — [StandardProcess.py:45](src/reagent/StandardProcess.py#L45) empty helper.

⚠️ **[Low] `BRDevrun` feedback variable** — the local `feedback` string (L137) is reassigned in the feedback branch (L150) but never passed to the first-iteration artifact runs. The feedback text reaches the LLM only via `modify_agent`.

⚠️ **[Low] `CompetitiveAnalysis` half-gone** — commented in [StandardProcess.py:142](src/reagent/StandardProcess.py#L142) but `get_competitive_analysis()` still appears in [util/util.py](src/util/util.py) and `get_reference` still describes it. Decide: delete or wire up.

### 6.3 Fragility

⚠️ **[High] Worker blocked indefinitely on disconnect** — `slot["event"].wait()` at an interrupt has no timeout. A browser close during review leaves the worker hanging until process restart.

⚠️ **[Medium] `stream_manager.remove_queue` never called** — queues accumulate over the process lifetime.

⚠️ **[Medium] `add_subchapter` off-by-one** — [src/util/doc_template/document.py:40](src/util/doc_template/document.py#L40) uses `len(SUBCHAPTERS) + 1` after appending, so the second chapter added receives SECTION `"3"` not `"2"`. Check whether callers set SECTION explicitly before `add_subchapter` — in the Initial/IEEE templates the SECTION is set in the constructor, making this line cosmetic.

⚠️ **[Medium] Hardcoded 4-level skeleton parser** — [src/util/doc_template/document.py:110](src/util/doc_template/document.py#L110) `parse_skeleton_to_document_template` only walks 4 depths; deeper JSON silently loses data.

⚠️ **[Low] Single-worker scalability** — deliberately `max_workers=1` to avoid state clobbering. Accepted today; future multi-project requires deeper refactor (Celery, process isolation).

### 6.4 Inconsistent Docs vs Code

- README.md §Tech Stack lists `CrewAI 1.6.x`; [pyproject.toml](pyproject.toml) pins `crewai[tools]==1.6.0` but [requirements.txt](requirements.txt) has `crewai==1.6.1`. Minor drift.
- [API_Readme.md](API_Readme.md) references `/artifacts/{project_id}/{name}` with `name` as artifact key; [backend/services/artifact_service.py](src/backend/services/artifact_service.py) treats names case-sensitively — document if users should expect normalization.

### 6.5 Security

⚠️ CORS wildcard, no auth, MongoDB auth disabled. Deployment context (intranet + SSH tunnel) assumes these; must harden for any public exposure.

---

## 7. Navigation Index

### Documentation
- [Agent.md](Agent.md) — one-page index
- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture
- [README.md](README.md) — user quick start
- [API_Readme.md](API_Readme.md) — HTTP API reference
- [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md) — deployment
- [frontend_integration_guide.md](frontend_integration_guide.md) — frontend

### Per-module design
- [docs/design-doc/backend.md](docs/design-doc/backend.md)
- [docs/design-doc/pipeline.md](docs/design-doc/pipeline.md)
- [docs/design-doc/util.md](docs/design-doc/util.md)
- [docs/design-doc/frontend_integration.md](docs/design-doc/frontend_integration.md)

### References
- [docs/references/api.md](docs/references/api.md)
- [docs/references/deployment.md](docs/references/deployment.md)
- [docs/references/artifacts.md](docs/references/artifacts.md)

### Code entry points
- [backend/main.py](src/backend/main.py) — FastAPI bootstrap
- [backend/services/execution.py](src/backend/services/execution.py) — pipeline orchestration
- [src/reagent/main.py](src/reagent/main.py) — CLI entry + SRS chapter loop
- [src/reagent/StandardProcess.py](src/reagent/StandardProcess.py) — stages 1–4 + modify_agent
- [util/__init__.py](src/util/__init__.py) — `run_with_retry`, `get_reference`, template factories
- [util/util.py](src/util/util.py) — thread-safe paths + `multiline_input`
- [util/DAG.py](src/util/DAG.py) — topological sort + dependency BFS
- [util/SoftwareManager.py](src/util/SoftwareManager.py) — CrewAI base class
