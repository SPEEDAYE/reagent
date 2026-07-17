# 2026-04-12 — Test & Deploy Pipeline-Hang Fix

## Goal

Ship the fixes from [2026-04-12-fix-pipeline-hang.md](2026-04-12-fix-pipeline-hang.md) to the shared production server `se.aiseclab.cn:10122`.

## Pre-Deploy Testing

| # | Test | Why |
|---|------|-----|
| 1 | Syntax check all modified Python files via `ast.parse` | Catch typos/indent errors before remote install |
| 2 | Import smoke test in `crewAI_BASE` conda env: import `util.SoftwareManager`, `src/reagent/BusinessRequirements`, `src/reagent/NonStandardProcess`, `backend.main` | Confirm `build_optional_tools` resolves and no downstream ImportError remains |
| 3 | Optional: `python script/api_smoke_test.py quick` against `http://localhost:8000` (only if local MongoDB + API running) | End-to-end CRUD sanity |
| 4 | `./deploy.sh pack` dry run | Confirms tarball builds cleanly; zero remote side effects |

Only if 1–4 pass, proceed to deploy.

## Deploy

```bash
REMOTE_PASS='<password from DEPLOY_GUIDE.md>' ./deploy.sh
```

This runs: pack → upload → remote install+restart → verify.

## Post-Deploy Verification

1. `curl http://localhost:8000/health` via SSH tunnel (or gh_action to the server) — expect `{status:healthy, db_connected:true}`.
2. On the server: `tail -n 50 /home/carl/reagent/reagent-api.log` — look for uvicorn startup line + no ImportError traceback.
3. (Optional) Create a throwaway project and subscribe to SSE — confirm events flow past Stage 1 / into Stage 2 (which is the part that used to hard-fail on `build_optional_tools`).

## Rollback

If the new binary breaks the server:
- `ssh carl@...` → `cd /home/carl/reagent && ./stop.sh`
- The tarball is named `reagent1.0_UI.tar.gz` — previous content is overwritten; rollback requires re-packing the previous commit. Mitigation: git is not initialized in the reagent1.0_UI dir, so save a timestamped backup on the server first.

## Progress

- [x] Step 1 — Syntax check (ast.parse on all modified files — PASS)
- [x] Step 2 — Import smoke test in crewAI_BASE
  - ✅ `util.SoftwareManager.build_optional_tools()` returns `[]`
  - ✅ `BusinessRequirements` module imports (the previously-broken path)
  - ✅ `NonStandardProcessrun` has 0 redundant outer loops, 1 inner loop
  - ✅ `StandardProcess` imports (transitively imports `from BusinessRequirements import *`)
  - ⚠ `backend.main` import skipped locally — fastapi lives in python3.10 user-site, crewAI_BASE is 3.12. Remote venv has `requirements_deploy.txt` installed so this is a local-env gap only. All 4 modified backend files verified via AST + symbol presence.
- [ ] Step 3 — Skipped (no local API running)
- [ ] Step 4 — `./deploy.sh pack` dry run
- [ ] Step 5 — Full `./deploy.sh`
- [ ] Step 6 — Post-deploy verification
- [ ] Step 7 — Update this plan + parent fix plan status
