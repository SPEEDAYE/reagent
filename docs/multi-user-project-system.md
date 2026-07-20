# Multi-user project and pipeline system

## Runtime model

- FastAPI remains the HTTP/SSE API process.
- Every pipeline run receives a unique `run_id`.
- Pipeline work runs in a spawned `ProcessPoolExecutor`; process-global CrewAI
  paths, environment variables and monkey patches are isolated per worker.
- Worker events and human feedback cross the process boundary through dedicated
  Manager queues. One project's feedback queue is never shared with another.
- Project status is a compatibility summary. `pipeline_runs` is the source of
  truth for execution history.
- Lifecycle events are stored in `pipeline_events` for seven days. Token chunks
  remain in-memory only to avoid excessive database writes.

## Ownership and authentication

All project, run, SSE, artifact and upload routes call the same ownership check.
An authenticated caller receives `404` for a foreign project so project IDs
cannot be enumerated.

The backend accepts either:

1. HS256 JWT or `base64(payload).HMAC-SHA256` tokens using
   `AUTH_TOKEN_SECRET`; or
2. gateway-injected identity headers protected by `AUTH_PROXY_SHARED_SECRET`.

Production must set `AUTH_REQUIRED=1`. `AUTH_REQUIRED=0` exists only for the
current migration window and permits deprecated calls carrying `user_id`.

## Primary API

```text
POST   /project/create
GET    /project/list
GET    /project/active
GET    /project/{project_id}
PATCH  /project/{project_id}
DELETE /project/{project_id}

GET    /project/{project_id}/runs
GET    /project/{project_id}/runs/{run_id}
GET    /project/{project_id}/runs/{run_id}/events

GET    /artifacts/{project_id}/{artifact_name}/versions
POST   /artifacts/{project_id}/{artifact_name}/versions
GET    /artifacts/{project_id}/{artifact_name}/versions/compare
GET    /artifacts/{project_id}/{artifact_name}/versions/{version}
POST   /artifacts/{project_id}/{artifact_name}/versions/{version}/restore

POST   /graph/stream/create
POST   /graph/stream/resume
POST   /graph/stream/cancel
GET    /graph/stream/{project_id}
```

`GET /project/list` supports `page`, `page_size`, `q`, `status`, `archived`,
`sort_by` and `sort_order`. The temporary `user_id` query is ignored as an
authority source in strict mode and must match the authenticated identity.

## Artifact versions

Artifact versions are scoped by `project_id`, `run_id`, and `artifact_name`.
The generated file is registered lazily as v1. Editing creates an immutable
new version in the configured database and does not overwrite pipeline output. Restoring an old
version also creates a new latest version, preserving the audit trail.

Clients send `base_version` when saving or restoring. The API returns HTTP 409
if another client has already saved a newer version. Version comparison returns
a unified diff and addition/deletion counts. Every route applies the same
project ownership check as project and run APIs.

## Concurrency and quota

- `PIPELINE_MAX_WORKERS` controls global worker-process concurrency.
- `PIPELINE_MAX_ACTIVE_PER_USER` controls queued/running runs per user.
- An atomic `(user_id, active_slot)` unique constraint prevents multi-tab
  races from exceeding the per-user quota.
- Excess tasks receive HTTP 429. Tasks waiting for a global worker remain
  `queued`; the frontend displays this state instead of treating it as stuck.

## Deployment checklist

Local downloads use embedded SQLite by default and create `data/reagent.db`
automatically. Set `DATABASE_TYPE=mongodb` only for an existing MongoDB
deployment; Mongo mode additionally requires `requirements-mongo.txt`.

1. Back up the configured database and deploy the backend once to create indexes.
2. Configure token verification or trusted gateway headers.
3. Set `AUTH_REQUIRED=1` and restart the API.
4. Start with `PIPELINE_MAX_WORKERS=2`; raise it only after observing memory and
   LLM-provider rate limits.
5. Verify two users can run projects concurrently and cannot retrieve each
   other's project, SSE, artifacts, files or run history.
6. After all clients use `/project/list` and `/project/active`, remove the
   deprecated `/{user_id}` endpoints and compatibility request fields.
