# script/

Scripts in this directory call the root `main.py` entry point.

| Script | Purpose |
|---|---|
| `start-api.sh` | Start the FastAPI server through `python main.py serve`. |
| `stop-api.sh` | Stop the API process recorded in `logs/reagent-api.pid`. |
| `restart-api.sh` | Stop and start the API server. |
| `status-api.sh` | Check local API process and `/health`. |
| `deploy.sh` | Build a local tarball for deployment. |
| `api_smoke_test.py` | API smoke-test helper, invoked with `python main.py smoke`. |
| `example_client.py` | Manual API demo client. |
