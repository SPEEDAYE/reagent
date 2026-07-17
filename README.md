# REagent

REagent is an AI-assisted requirements engineering system built with CrewAI and FastAPI. It turns a project description into requirements artifacts such as market research, BRD sections, use cases, non-functional requirements, diagrams, and SRS chapters.

This repository has been restructured as an academic code repository. The root `main.py` is the single program entry, `script/` contains runnable scripts, `dataset/` records inputs, and `experiment/` stores one run folder per execution.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py serve --host 0.0.0.0 --port 8000
```

CLI run:

```bash
python main.py \
  --project_name "My Project" \
  --description_file "dataset/requirements/software_analysis.txt" \
  --srs_example_path "src/util/doc_template/document_example.md"
```

Smoke test:

```bash
python main.py smoke quick
```

## Standard Layout

| Path | Purpose |
|---|---|
| `main.py` | Unified entry for CLI, API server, and smoke-test dispatch. |
| `script/` | Shell/Python scripts that call `main.py`. |
| `dataset/` | Requirement briefs, sample inputs, and dataset provenance. |
| `baseline/` | Baseline and comparison-system notes. |
| `experiment/` | Per-run outputs. Each run has `README.md` and `command.txt`. |
| `src/reagent/` | CrewAI requirement-engineering pipeline. |
| `src/backend/` | FastAPI, SSE, MongoDB, and artifact APIs. |
| `src/util/` | DAG, document templates, LLM config, and shared utilities. |
| `src/config/` | Agent/task/tool/skill configuration and tool contracts. |
| `docs/` | Code-repository docs, execution docs, design docs, visualization. |
| `context/` | Architecture and current working context. |

## Runtime Artifacts

API runs write artifacts to `experiment/{project_id}/`.

CLI runs create `experiment/<YYYYMMDD-HHMMSS>-<script-id>-<model-id>/`.

Generated logs, uploaded files, CrewAI storage, template caches, `.env`, and pickle outputs are ignored by Git.

## Documentation

- `AGENT.md` is the short repository index.
- `docs/index.md` is the documentation map.
- `docs/system-visualization/pipeline.md` describes the execution flow.
- `ai-interaction.md` records the synchronization rules for future AI-assisted changes.
