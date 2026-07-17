# REagent Repository Index

## One-Line Pitch

FastAPI + CrewAI pipeline for generating requirements-engineering artifacts from a natural-language project brief.

## Entry Points

| Purpose | Path |
|---|---|
| Unified entry | `main.py` |
| API server | `python main.py serve --host 0.0.0.0 --port 8000` |
| CLI pipeline | `python main.py --description_file dataset/requirements/software_analysis.txt` |
| Smoke test | `python main.py smoke quick` |
| Script index | `script/README.md` |

## Code Map

| Path | Role |
|---|---|
| `src/reagent/` | CrewAI pipeline stages and SRS generation. |
| `src/backend/` | FastAPI routes, services, DB access, SSE streaming. |
| `src/util/` | Shared utilities, document templates, LLM config, DAG rules. |
| `src/config/agent/` | CrewAI agent configuration. |
| `src/config/task/` | CrewAI task prompt configuration. |
| `src/config/tool/` | Agent-callable tool contracts and implementations. |
| `src/config/skill/` | Project-specific skill/context snippets. |

## Academic Repo Map

| Path | Role |
|---|---|
| `dataset/requirements/` | Natural-language project briefs. |
| `dataset/samples/` | Small sample files used for demos. |
| `baseline/` | Baseline systems and comparison notes. |
| `experiment/` | Single-run output directories with metadata. |
| `docs/design-doc/` | Module design notes. |
| `docs/exec-doc/` | Execution plans and change records. |
| `docs/system-visualization/` | Pipeline, code function, LLM call, and external call maps. |
| `context/` | Current architecture and feature context. |

## Runtime Invariants

- `main.py` is the only root program entry.
- Scripts in `script/` call `main.py`.
- API artifacts are stored under `experiment/{project_id}/`.
- CLI artifacts are stored under timestamped `experiment/<run-id>/` directories.
- Runtime secrets and bulky outputs stay out of Git via `.gitignore`.
