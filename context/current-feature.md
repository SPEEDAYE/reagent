# Current Feature

## Active Focus

Academic repository restructuring based on `routine_skill/academic_skills`.

## Current State

- Root `main.py` is the unified entry.
- Shell scripts live under `script/`.
- Inputs live under `dataset/`.
- Outputs live under `experiment/`.
- Implementation packages live under `src/`.
- Agent, task, tool, and skill configuration lives under `src/config/`.

## Follow-Up Candidates

- Convert historical design/reference docs into shorter current docs.
- Add a tiny no-LLM unit test for path initialization.
- Add explicit baseline comparison records if a paper evaluation is planned.
