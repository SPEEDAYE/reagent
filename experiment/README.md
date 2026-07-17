# experiment/

Each execution writes one run directory.

CLI run id format:

```text
<YYYYMMDD-HHMMSS>-<script-id>-<model-id>/
```

API runs use the project id as the run id:

```text
experiment/<project_id>/
```

Each run directory must include:

- `README.md`
- `command.txt`
- Generated artifacts and small reproducibility metadata

Large logs, pickle files, CrewAI storage, and bulky generated outputs are ignored by Git.
