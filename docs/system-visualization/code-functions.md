# Code Functions

| Component | Function |
|---|---|
| `main.py` | Dispatches CLI, API server, and smoke-test flows. |
| `src/reagent/main.py` | Runs CLI pipeline and initializes experiment run metadata. |
| `src/backend/services/execution.py` | Runs API-triggered pipeline in a worker thread and emits SSE events. |
| `src/util/util.py` | Manages per-run artifact paths and interrupt/resume state. |
| `src/util/DAG.py` | Stores artifact dependency rules and topological ordering helpers. |
| `src/reagent/logger.py` | Writes structured run logs with secret redaction. |
| `src/reagent/progress.py` | Emits terminal or JSON progress frames. |
