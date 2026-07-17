# Utility Layer Design

> Scope: [../../util/](../../src/util/). Shared building blocks: thread-safe state, DAG, LLM config, document templates.

## 1. Package Surface — [util/\_\_init\_\_.py](../../src/util/__init__.py)

Aggregates utilities into a single namespace used by pipeline modules (`from util import *`).

| Export | Origin | Purpose |
|--------|--------|---------|
| `run_with_retry` | [__init__.py:21](../../src/util/__init__.py#L21) | Crew execution wrapper (5 retries, 15 s delay) with optional `post_process` |
| `get_reference` | [__init__.py:108](../../src/util/__init__.py#L108) | Builds Chinese-language artifact context string for LLM prompts; optional `artifact=True` inlines content |
| `get_br_Initial_Template(authors)` / `get_srs_IEEE_Template(authors)` / `get_srs_Initial_Template(authors)` | [__init__.py:10–17](../../src/util/__init__.py#L10) | Template factories delegating to `doc_template/*` |
| all of `util.util.*`, `util.DAG.*`, `util.Artifacts.*`, `util.validate_format.*` | `from … import *` | Re-exported for pipeline convenience |

## 2. Thread-Safe Path State — [util/util.py](../../src/util/util.py)

```python
_thread_local = threading.local()
_global_store_path = "output"

def get_store_path() -> str:
    return getattr(_thread_local, 'store_path', _global_store_path)

def set_store_path(path: str):
    _thread_local.store_path = path
    _global_store_path = path
    os.makedirs(path, exist_ok=True)
```

**Why both thread-local AND global?** CrewAI internally spawns helper threads (telemetry, embedding). Those threads do not inherit the thread-local, so they fall back to the latest global — good enough because the single-worker executor means only one project's path is ever active at once.

### Feedback slot API (used by backend)

| Function | Caller | Purpose |
|----------|--------|---------|
| `register_feedback_slot(pid)` | Backend `ExecutionService.start` | Creates `{event: threading.Event(), value: None}` entry in `_feedback_registry` |
| `submit_feedback(pid, value)` | Backend `ExecutionService.resume` | Sets value + signals event |
| `set_stream_callback(callback)` | Backend once at start | Stores `_stream_callback = _emit` so `multiline_input` can emit SSE |
| `multiline_input(prompt_text, project_id, interrupt_data)` | Pipeline at interrupt points | CLI mode: `prompt_toolkit` interactive input. API mode: emit `interrupt` SSE + `event.wait()` |

### Artifact getters

Lazy readers of `{store_path}/<name>.md` or `.pkl`. Examples: `get_survey`, `get_BRD`, `get_ERD`, `get_SRS_chapter`, `get_SRS_planning`, `get_document_skeleton`, `get_artifact_planing`, `get_user_case`, `get_non_functional_requirements` …

Parsers:
- `split_markdown_by_h2(md)` — splits by `## ` headers (L126).
- `parse_artifact_dependencies(raw)` — strips comments, uses `ast.literal_eval` (L132).
- `print_doc_content(d)` — formats chapter plan dict to text (L40).

## 3. SoftwareManagerCrew Base Class — [util/SoftwareManager.py](../../src/util/SoftwareManager.py)

```python
class SoftwareManagerCrew:
    agents: List[BaseAgent]
    tasks: List[Task]
    llm = build_llm()           # class-level; shared across all subclasses

    @agent
    def SoftwareManager(self) -> Agent:
        return Agent(config=self.agents_config["SoftwareManager"],
                     llm=self.llm, verbose=True, use_agent_data=False)

    @before_kickoff
    def before_kickoff_function(self, inputs): return inputs

    @after_kickoff
    def after_kickoff_function(self, result): return result

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks,
                    process=Process.sequential, verbose=True)
```

Subclasses add their own `@agent`/`@task` methods and set `self.agents`/`self.tasks`. Hooks can be overridden.

## 4. LLM Configuration — [util/llm_config.py](../../src/util/llm_config.py)

### Env loading precedence

```
1. Workspace-level .env  (reagent1.0_UI/../.env) — lowest priority
2. Project-local   .env  (reagent1.0_UI/.env)    — overrides workspace
```

### Provider resolution

Env candidates checked in order: `LLM_PROVIDER`, `MODEL_PROVIDER`, `DEFAULT_LLM_PROVIDER`. Value lower-cased and resolved through `PROVIDER_ALIASES` ({"gpt": "openai", …}). Default: `"openai"`.

### Supported providers

| Provider | Default model | Model env keys | API-key env keys | base_url env keys |
|----------|--------------|----------------|-------------------|-------------------|
| openai | `o1` | `LLM_MODEL`, `OPENAI_MODEL` | `OPENAI_API_KEY`, `OPENAI_KEY` | `OPENAI_BASE_URL` |
| deepseek | `deepseek-chat` | `DEEPSEEK_MODEL`, `LLM_MODEL` | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL` |
| qwen | `qwen-plus` | `QWEN_MODEL` | `QWEN_API_KEY` | `QWEN_BASE_URL` |
| ucloud | `gpt-4o-mini` | `UCLOUD_MODEL` | `UCLOUD_API_KEY` | `UCLOUD_BASE_URL` |
| zhiyuan | `qwen3-max` | `ZHIYUAN_MODEL` | `ZHIYUAN_API_KEY` | `ZHIYUAN_BASE_URL` |

### `build_llm()`

Constructs `crewai.LLM(**kwargs)` with `provider="openai"` (hardcoded — CrewAI uses OpenAI-compatible API for all providers); optional `base_url`, `temperature`, `timeout`, `max_tokens`, `reasoning_effort`.

## 5. DAG Algorithms — [util/DAG.py](../../src/util/DAG.py)

### 5.1 `Artifact_Dependance_rules` (L4–21)

Dict: `artifact → list of direct deps`. This is the canonical dependency graph. Example: `"BRD": ["user_introduction", "feature_tree", "event_list", "context_diagram", "business_scope", "survey"]`.

### 5.2 `get_dependent_artifacts(changed, include_self=True)` (L23)

BFS over the **forward** graph (edge `dep → artifact`). Returns all artifacts transitively impacted by a change in `changed`.

### 5.3 `to_artifact_DAG(artifact_planning)` (L63)

Takes the chapter×artifact plan, fixed-point expands to include transitive deps, returns a reverse adjacency `{node: [predecessors]}` used as input to `topological_sort(…, reverse=True)`.

### 5.4 `topological_sort(graph, reverse=True)` (L107)

Kahn's algorithm. `reverse=True` interprets `graph[v] = predecessors`; `reverse=False` interprets it as successors. Raises on cycle.

### 5.5 `detect_dependency_cycles(dep_rules)` (L179)

DFS-based cycle detection; returns list of cycles (as lists of nodes). Used defensively when loading rules.

## 6. Document Template System — [src/util/doc_template/](../../src/util/doc_template/)

### 6.1 Classes

| Class | File | Role |
|-------|------|------|
| `paragraph` | [chapter.py:4](../../src/util/doc_template/chapter.py#L4) | Base: TITLE, INTRODUCTION, Structure, TIMESTAMP, SUBCHAPTERS, SECTION, WRITTEN |
| `CHAPTER(paragraph)` | [chapter.py:22](../../src/util/doc_template/chapter.py#L22) | Adds `add_subchapter`, `update_content`, `get_all_content` with markdown rendering |
| `Document` | [document.py:4](../../src/util/doc_template/document.py#L4) | Root: AUTHOR + SUBCHAPTERS; `write_file()`, `get_whole_document()` |
| `BusinessRequirement(Document)` | [BusinessRequirement/BR.py](../../src/util/doc_template/BusinessRequirement/BR.py) | Marker subclass |
| `SoftwareRequirementSpecification(Document)` | [SoftwareRequirementSpecification/SRS.py](../../src/util/doc_template/SoftwareRequirementSpecification/SRS.py) | Marker subclass |

### 6.2 Template Factories

- `Create_BR_Initial_Template(authors)` — [BusinessRequirement/Initial_template.py:5](../../src/util/doc_template/BusinessRequirement/Initial_template.py#L5). 3 chapters: Business requirements (7 subchapters), Scope and limitations (4), Business context (3).
- `Create_SRS_Initial_Template(authors)` — 7 top-level chapters.
- `Create_SRS_IEEE_Template(authors)` — 20 IEEE-830 chapters.

### 6.3 Skeleton Parser

`parse_skeleton_to_document_template(skeleton_json, authors)` ([document.py:110](../../src/util/doc_template/document.py#L110)) — consumes the JSON produced by `ExtractDocumentCrew` and builds a 4-level nested Document. **Hardcoded nesting depth** (⚠️ see Known Issues).

### 6.4 Rendering

`Document.get_whole_document(only_show_written=True)` concatenates `CHAPTER.get_all_content()` outputs. Markdown heading level is `len(SECTION.split('.'))`:
- `"1"` → `#`
- `"1.1"` → `##`
- `"1.1.1"` → `###`
- `"1.1.1.1"` → `####`

## 7. Minor Utilities

- [util/Artifacts.py](../../src/util/Artifacts.py) — `get_dependence_appendix(dep_list) -> str`. Renders the "附录：依赖项说明" section appended to BRD.md and SRS.md.
- [util/validate_format.py](../../src/util/validate_format.py) — `validate_use_case_format(use_cases)`. Strict schema check for use-case JSON.
- [util/user_case.py](../../src/util/user_case.py) — `UserCase` dataclass + `get_usecase()` render.

## 8. Known Issues (util)

- ⚠️ [chapter.py:34–46](../../src/util/doc_template/chapter.py#L34) — `get_last_content`, `get_all_content` (base class), `get_references` all reference non-existent attributes (`self.CONTENT`, `self.REFERENCE`). Dead code with latent `AttributeError` if ever invoked.
- ⚠️ [document.py:40](../../src/util/doc_template/document.py#L40) — `add_subchapter` sets `SECTION = len(SUBCHAPTERS) + 1` (off-by-one: after appending, length already includes the new element; second call to `add_subchapter` yields SECTION="3" instead of "2").
- ⚠️ [document.py:110](../../src/util/doc_template/document.py#L110) — skeleton parser hardcodes 4 nesting levels; deeper skeleton JSONs silently truncate.
- ⚠️ [util/__init__.py:65–106](../../src/util/__init__.py#L65) — large commented-out prior implementation of `get_reference`; should be deleted.
- ⚠️ No `__init__.py` in `src/util/doc_template/`, `src/util/doc_template/BusinessRequirement/`, `src/util/doc_template/SoftwareRequirementSpecification/` — they work as implicit namespace packages but are not PEP 328 compliant.
