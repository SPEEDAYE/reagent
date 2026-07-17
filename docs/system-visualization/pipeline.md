# Pipeline

## CLI Flow

```text
python main.py
  -> reagent.main.main()
  -> initialize experiment/<timestamp>-cli-<model>/
  -> StandardProcessrun()
  -> NonStandardProcessrun()
  -> RequirementSpecificationrun()
  -> experiment/<run-id>/*.md + command.txt + README.md
```

## API Flow

```text
python main.py serve
  -> backend.main:app
  -> POST /project/create
  -> POST /graph/stream/create
  -> ExecutionService.start()
  -> _run_pipeline(project_id, config)
  -> experiment/<project_id>/*.md + command.txt + README.md
  -> SSE stage/crew/artifact events
```

## Stages

1. Meta analysis
2. Business requirements
3. Requirement elicitation
4. Requirement analysis
5. Non-standard artifacts
6. SRS generation
