# User Interaction

REagent has three human-in-the-loop review points in API mode:

| Review | Artifact | Resume options |
|---|---|---|
| Business scope review | `business_scope.md` | `accept`, `feedback` |
| BRD review | `BRD.md` | `accept`, `feedback` |
| Elicitation review | `use_case.md`, `non_functional_requirements.md` | `accept`, `feedback` |

CLI mode prompts in the terminal. API mode emits SSE `interrupt` events and resumes through `POST /graph/stream/resume`.
