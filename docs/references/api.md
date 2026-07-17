# API Cheat Sheet

> Full reference: [../../API_Readme.md](../../API_Readme.md). This is a quick lookup for endpoints + SSE events.

## Endpoints

| # | Method | Path | Purpose |
|---|--------|------|---------|
| 1 | GET | `/health` | Service + DB status |
| 2 | POST | `/project/create` | Create project → `project_id` |
| 3 | GET | `/project/list/{user_id}` | List user's projects |
| 4 | GET | `/project/{project_id}` | Project detail |
| 5 | DELETE | `/project/{project_id}` | Delete project + artifacts + uploads |
| 6 | POST | `/graph/stream/create` | Start pipeline (async) |
| 7 | POST | `/graph/stream/resume` | Submit interrupt feedback |
| 8 | GET | `/graph/stream/{project_id}` | SSE event stream |
| 9 | GET | `/artifacts/{project_id}` | List artifacts + DAG |
| 10 | GET | `/artifacts/{project_id}/{name}` | Artifact content (markdown) |
| 11 | POST | `/artifacts/export_pdf` | PDF export (binary) |
| 12 | POST | `/files/upload` | Upload data file or SRS template |

## Request Schemas

`POST /project/create` body:
```json
{
  "user_id": "string",
  "project_name": "string",
  "description": "string",
  "srs_template": "IEEE" | "Initial" | null
}
```

`POST /graph/stream/create` body:
```json
{
  "project_id": "string",
  "user_id": "string",
  "human_request": "string (optional)"
}
```

`POST /graph/stream/resume` body:
```json
{
  "project_id": "string",
  "resume_type": "accept" | "feedback" | "skip" | "redo_artifact",
  "human_comment": "string (required for feedback/redo_artifact)"
}
```

## SSE Event Lifecycle

```
connected
→ stage_start (stage=meta_analysis, 1/6)
  → crew_start / artifact_complete (×N)
→ stage_complete (stage=meta_analysis)

→ stage_start (stage=business_requirements, 2/6)
  → crew_start / artifact_complete (×N)
  → interrupt (business_review)            ⇠ POST /graph/stream/resume
  → crew_start / artifact_complete (×N)    ← BRD generation
  → interrupt (brd_review)                 ⇠ POST /graph/stream/resume
→ stage_complete

→ stage_start (stage=requirement_elicitation, 3/6)
  → ...
  → interrupt (elicitation_review)          ⇠ POST /graph/stream/resume
→ stage_complete

→ stage_start (stage=requirement_analysis, 4/6) → stage_complete
→ stage_start (stage=non_standard, 5/6) → stage_complete
→ stage_start (stage=srs_generation, 6/6) → stage_complete
→ finished (total_artifacts=17, srs_generated=true)
```

## Error Events

```json
{ "type": "error", "error": "...", "recoverable": true|false, "crew_name": "..." }
```

- `recoverable=true`: transient (emitted by patched `run_with_retry` wrapper on single-crew failure). Pipeline continues.
- `recoverable=false`: terminal (stage-level exception bubbled up). Pipeline stopped; status = `error`.

## Testing

- `python example_client.py quick` — CRUD smoke test
- `python example_client.py` — full pipeline demo with auto-approval
- `python script/api_smoke_test.py quick` — pytest-style CRUD
- `python script/api_smoke_test.py pipeline --auto-accept --cleanup` — full flow
