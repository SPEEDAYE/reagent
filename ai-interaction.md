# AI Interaction

## Workflow Routing

| Task Type | Workflow |
|---|---|
| Code changes | Read local code, edit scoped files, run smoke or import checks. |
| Experiment changes | Update `main.py`/`script/`, record run metadata in `experiment/`. |
| Dataset changes | Update `dataset/README.md` with source, license, version, and local path. |
| Agent/task/tool changes | Update `src/config/` and synchronize `docs/system-visualization/`. |
| API behavior changes | Update `src/backend/`, API docs, and smoke-test commands. |
| Documentation-only changes | Update `docs/`, `context/`, and this file as needed. |

## Documentation Sync Matrix

| Change | Sync |
|---|---|
| Entry command or script | `README.md`, `script/README.md`, `docs/system-visualization/pipeline.md` |
| Artifact path | `README.md`, `experiment/README.md`, `src/backend/config.py` |
| CrewAI task or prompt | `src/config/task/`, `docs/system-visualization/llm-calls/` |
| Tool contract | `src/config/tool/`, `docs/system-visualization/external-calls.md` |

## Verification Commands

```bash
python -m compileall main.py src script
python main.py smoke quick
```
