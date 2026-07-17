# 2026-04-12 — Fix Pipeline Hang Reported by 刘小松

## Context — What the Debugger Reported

- Direct connection (not forwarded via nginx).
- After calling `POST /graph/stream/create`, SSE stream emits events at a steady **15-second interval** (screenshot timestamps: 10:23:22 → 10:23:37 → 10:23:52 → 10:24:07 → 10:24:22).
- `GET /artifacts/{pid}` returns all artifacts with `status: "pending"`.
- State has been unchanged since the previous night.
- User did **not** upload a file — pipeline uses default `srs_example_path`.
- Conclusion from user: "pending 是卡死了吗" (is pending frozen?). Assistant answered it means "not yet generated."

## Root-Cause Diagnosis

### Primary: `build_optional_tools` ImportError

[src/reagent/BusinessRequirements.py:27](../../src/reagent/BusinessRequirements.py#L27) imports:
```python
from util.SoftwareManager import SoftwareManagerCrew, build_optional_tools
```
But `build_optional_tools` is **not defined anywhere in the repo** (confirmed via repo-wide grep). When the backend's worker thread tries
`from StandardProcess import MetaAnalysisrun` at [backend/services/execution.py:178](../../src/backend/services/execution.py#L178), Python transitively imports `BusinessRequirements` (via `StandardProcess`'s top-level `from BusinessRequirements import *`), which raises `ImportError: cannot import name 'build_optional_tools'`.

The exception is caught by the outer `try/except` at `_run_pipeline` L166. An `error` SSE with `recoverable=False` is emitted at L303, and the pipeline stops.

### Secondary: Invisible error after reconnect

sse-starlette's `EventSourceResponse` sends a keep-alive comment (`: ping\n\n`) every **15 seconds** by default. If the user saw (or missed) the error event on their first SSE subscription and later reconnected:
- Queue is still in `stream_manager._queues[pid]` (cleanup code path never runs `remove_queue`).
- Queue is empty now (earlier events already consumed).
- `subscribe()` yields `connected`, then blocks forever on `queue.get()`.
- sse-starlette emits 15-second pings to keep the connection alive.

This matches the user's observation exactly. The "15-second events" are keep-alive pings, not progress events. The pipeline is not running at all.

### Tertiary: Duplicate outer loop

[src/reagent/NonStandardProcess.py:54–57](../../src/reagent/NonStandardProcess.py#L54) contains:
```python
for artifact in artifact_dict:        # outer: rebinds `artifact` to a key
    for artifact in order:            # inner: rebinds again
        if artifact in artifact_dict.keys():
            artifact_dict[artifact].run()
```
Each NonStandard artifact runs `len(artifact_dict) = 2` times once Stage 5 executes. Not the cause of the current hang, but it's a real bug that should be fixed together.

## Plan

| # | Change | File | Rationale |
|---|--------|------|-----------|
| 1 | Add `build_optional_tools()` returning `[]` by default; optionally returns `[WebsiteSearchTool()]` when `ENABLE_WEBSITE_SEARCH_TOOL` env is truthy | [util/SoftwareManager.py](../../src/util/SoftwareManager.py) | Unblocks the ImportError. Default-off keeps behavior unchanged for existing deployments. |
| 2 | Persist `last_error` on the project document when a non-recoverable error is emitted | [backend/services/execution.py](../../src/backend/services/execution.py) | Makes errors observable via `GET /project/{pid}` even if SSE subscriber missed the event. |
| 3 | On SSE subscribe, if the project's status is already `error` or `finished`, yield a synthetic replay event (with `last_error` or `finished`) and close instead of waiting for events forever | [backend/api/routes/stream.py](../../src/backend/api/routes/stream.py) | Eliminates the "silent pings after terminal state" failure mode. |
| 4 | Remove the outer `for artifact in artifact_dict:` loop in NonStandardProcessrun | [src/reagent/NonStandardProcess.py](../../src/reagent/NonStandardProcess.py) | Fixes double-execution bug. |
| 5 | Update [reagent1.0_UI-report.md](../../reagent1.0_UI-report.md) and [README.md](../../README.md) to mark these issues as FIXED | docs | Keep docs in sync. |

### Non-changes

- We do **not** change the 15-second SSE ping default — it's the expected keep-alive behavior of sse-starlette.
- We do **not** touch the `CLI skips BRDev` issue — that's a separate documented behavior and the user is on the API path.

## Progress

- [x] Step 1 — Add `build_optional_tools()` to util/SoftwareManager.py
- [x] Step 2 — Persist last_error on project
- [x] Step 3 — Replay terminal state on subscribe
- [x] Step 4 — Fix NonStandardProcess double loop
- [x] Step 5 — Update docs (report + README + exec-plans index)
- [x] Post-check: grep confirms no remaining undefined imports; docs cross-refs intact

## Verification Steps (for the debugger)

1. Restart the API server.
2. Create a new project and start the pipeline: `POST /graph/stream/create`.
3. Subscribe to SSE: `GET /graph/stream/{pid}`. Should see progress events, not just pings.
4. If any error occurs, `GET /project/{pid}` now includes `last_error` field.
5. Reconnecting SSE after the pipeline has terminated will immediately emit the final state and close, instead of hanging.

## Open Follow-ups (out of scope for this plan)

- Add a timeout + automatic-fail option to `multiline_input`'s `event.wait()` so disconnected frontends don't hang the worker indefinitely.
- Call `stream_manager.remove_queue(pid)` after a grace period post-`finished`/`error` to free memory.
- Fix `CLI skips BRDev` (StandardProcessrun missing BRDevrun call) — separate plan.
