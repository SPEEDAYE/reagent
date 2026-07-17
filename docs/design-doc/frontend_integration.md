# Frontend Integration — SSE Contract

> This is a design-level summary. For TypeScript examples, see [../../frontend_integration_guide.md](../../frontend_integration_guide.md).

## 1. Flow Overview

```
1. POST /project/create                 → project_id
2. (optional) POST /files/upload        → upload data or custom SRS template
3. POST /graph/stream/create            → starts pipeline asynchronously
4. GET  /graph/stream/{project_id}      → long-lived SSE connection
     ├── connected
     ├── stage_start × 6 (with stage_complete)
     ├── crew_start / artifact_complete × N (one per run_with_retry call)
     ├── interrupt × 3 (requires POST /graph/stream/resume to continue)
     ├── error (recoverable=True → recoverable; False → terminal)
     ├── completed (success terminal)
     └── finished (legacy success terminal)
5. GET  /artifacts/{pid}                → browse results + DAG
6. GET  /artifacts/{pid}/{name}         → individual markdown
7. POST /artifacts/export_pdf           → download PDF
```

## 2. SSE Event Types

| Event | Fields | When |
|-------|--------|------|
| `connected` | `project_id` | Immediately after subscribe |
| `stage_start` | `stage`, `stage_index` (1–6), `total_stages` (6), `stage_label` (Chinese) | Entering a stage |
| `crew_start` | `crew_name`, `stage` | Each `run_with_retry` begins |
| `artifact_complete` | `crew_name` | Each `run_with_retry` succeeds |
| `interrupt` | `interrupt_type` (business_review / brd_review / elicitation_review), `artifact_names`, `message`, `options` | Pipeline blocked on user review |
| `stage_complete` | `stage` | Stage finished |
| `error` | `error`, `recoverable` (bool), optional `crew_name` | Crew or stage failed |
| `completed` | `status`, `total_artifacts` (17), `srs_generated` (bool) | Pipeline done |
| `finished` | `status`, `total_artifacts` (17), `srs_generated` (bool) | Legacy success terminal |

All events carry a `timestamp` (UTC ISO) injected by [StreamManager](../../src/backend/services/stream_manager.py#L37).

## 3. Interrupt Protocol

```typescript
es.addEventListener("interrupt", async (e) => {
  const { interrupt_type, artifact_names, message, options } = JSON.parse(e.data);
  // Fetch artifact content for review
  const art = await fetch(`/artifacts/${pid}/${artifact_names[0]}`).then(r => r.json());
  // Show dialog with art.content (markdown + Mermaid)
  // Submit decision:
  await fetch(`/graph/stream/resume`, {
    method: "POST",
    body: JSON.stringify({
      project_id: pid,
      resume_type: "accept" | "feedback" | "skip" | "redo_artifact",
      human_comment: "..." // for feedback / redo_artifact
    }),
  });
  // SSE continues automatically.
});
```

`resume_type` mapping (handled in [backend/services/execution.py:82](../../src/backend/services/execution.py#L82)):

| resume_type | Value sent to `multiline_input` | Worker behavior |
|-------------|--------------------------------|-----------------|
| `accept` | `"no"` | Proceed to next stage |
| `feedback` | `human_comment` (or `"no"` if absent) | `modify_agent(feedback)` → regenerate affected artifacts → re-enter review |
| `redo_artifact` | `human_comment` (or `"redo"`) | Same path as feedback |
| `skip` | `"exit"` | Worker calls `exit()` — ⚠️ terminates worker; pipeline ends |

## 4. Nginx Requirements

SSE requires:
```nginx
proxy_http_version 1.1;
proxy_set_header Connection '';
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 86400s;   # 30-min pipelines must not timeout
```

See [../../frontend_integration_guide.md](../../frontend_integration_guide.md) §Nginx-Config.

## 5. Content Rendering

Artifacts are markdown. Several embed **Mermaid** fenced code blocks:

| Artifact | Diagram type |
|----------|--------------|
| `context_diagram` | System context |
| `data_flow_diagram` | DFD |
| `entity_relationship_diagram` | ERD |
| `state_transition_diagram` | State machine |
| `dialog_map` | UI flow |

Recommended stack: `react-markdown` + `remark-gfm` + `mermaid.js`. For the artifact dependency DAG view, use `vis-network`, `reactflow`, or `d3-dag`.

## 6. State Management Hints

Maintain a state machine:

```
IDLE → CREATING → RUNNING ↔ INTERRUPTED
                          ↘ COMPLETED
                          ↘ ERROR
```

`RUNNING → INTERRUPTED`: on `interrupt` event.
`INTERRUPTED → RUNNING`: after `POST /graph/stream/resume` returns 200.
Terminal states: `COMPLETED` (on `completed`, with `finished` kept for legacy listeners), `ERROR` (on `error` with `recoverable=false`).

## 7. Reconnection

Native `EventSource` auto-reconnects on network drops. If you need manual handling (e.g., reverse-proxy gap), read the last event's timestamp and request a resume — but note that the backend **does not replay** missed events (no event log). Missing events between disconnect and reconnect are lost.

⚠️ If the user closes the browser during an interrupt, the worker remains blocked on `event.wait()` until the server process restarts.
