# CrewAI Pipeline Design — 6 Stages, 17 Artifacts

> Scope: [../../src/reagent/](../../src/reagent/). The "brain" of REagent: CrewAI agents that read prior artifacts and write the next one.

## 1. Overview

A single natural-language project description is transformed into a complete IEEE-style SRS via 6 sequential stages. 3 human-in-the-loop interrupts allow users to correct course before downstream artifacts are generated.

```
Description → MetaAnalysis → BRDev → Elicitation → Analysis → NonStandard → SRS Generation
                  L1            L2       L3          L4          L5           L6
                               ★2        ★1
                                         ★ = interrupt
```

## 2. Stage Anchors

| # | Stage | Entry function | File | Artifacts produced |
|---|-------|----------------|------|--------------------|
| 1 | MetaAnalysis | `MetaAnalysisrun` | [StandardProcess.py:48](../../src/reagent/StandardProcess.py#L48) | document_template (object), document_skeleton.md, doc_content.md, chapter_dependence.md, artifact_planning |
| 2 | BusinessRequirements | `BRDevrun` | [StandardProcess.py:135](../../src/reagent/StandardProcess.py#L135) | survey, context_diagram, event_list, user_introduction, feature_tree, business_scope, BRD |
| 3 | RequirementElicitation | `RequirementElicitationrun` | [StandardProcess.py:235](../../src/reagent/StandardProcess.py#L235) | use_case, non_functional_requirements |
| 4 | RequirementAnalysis | `RequirementAnalysisrun` | [StandardProcess.py:277](../../src/reagent/StandardProcess.py#L277) | data_dictionary, ERD, data_flow_diagram, functional_requirements, dialog_map (in topological order) |
| 5 | NonStandardProcess | `NonStandardProcessrun` | [NonStandardProcess.py](../../src/reagent/NonStandardProcess.py) | usage_scenario, state_transition_diagram |
| 6 | SRS Generation | `RequirementSpecificationrun` | [main.py:24](../../src/reagent/main.py#L24) | SRS.md (chapter-by-chapter) |

## 3. CrewAI Class Hierarchy

All crews extend `SoftwareManagerCrew` (shared LLM + before/after hooks). See [util.md §3](util.md#3-softwaremanagercrew-base-class) for the base.

```
SoftwareManagerCrew [util/SoftwareManager.py]
├── MetaAnalysis.py
│   ├── ExtractDocumentCrew        → parses user-supplied SRS example into JSON skeleton
│   ├── DocContentCrew             → plans per-chapter content focus
│   ├── ChapterDependenceCrew      → infers chapter→chapter deps
│   └── ArtifactPlanningCrew       → maps chapters → required artifacts (list[list[str]])
│
├── BusinessRequirements.py
│   ├── SurveyCrew / surveyRun
│   ├── ContextDiagramCrew / ContextDiagramRun
│   ├── EventListCrew / eventlistRun
│   ├── UserIntroductionCrew / UserIntroductionRun
│   ├── FeatureTreeCrew / FeatureTreeRun
│   ├── BusinessScopeCrew / BusinessScopeRun
│   ├── BRDev                      → per-chapter BRD generator
│   ├── BRDModifyLocateCrew        → identifies which artifacts to regenerate
│   └── BRDModifyCrew              → actually regenerates them
│
├── RequirementElicitation.py
│   ├── UserCaseCrew / UserCaseRun
│   └── NFRCrew / NFRRun
│
├── RequirementAnalysis.py
│   ├── DataDictionaryCrew / datadictionaryRun
│   ├── ERDCrew / ERDRun
│   ├── DataFlowDiagramCrew / DataFlowDiagramRun
│   ├── FRCrew / FunctionRequirementRun
│   └── DialogMapCrew / DialogMaprun
│
├── NonStandardProcess.py
│   ├── UsageScenarioCrew
│   └── STDCrew                    → state transition diagram
│
└── RequirementSpecification.py
    ├── SRSplaningCrew             → per-chapter planning
    └── SRSev                      → per-chapter SRS writer
```

Agent/task prompts: [../../src/config/agent/agents.yaml](../../src/config/agent/agents.yaml) + [tasks.yaml](../../src/config/task/tasks.yaml) (Chinese, 26 tasks) / [tasks_eng.yaml](../../src/config/task/tasks_eng.yaml) (English).

## 4. Stage Walkthroughs

### 4.1 MetaAnalysis (L1)

`MetaAnalysisrun(doc_example_path, SRS_template, project_name, Description)`:
1. Computes SHA-256 hash — of `read_markdown(doc_example_path)` if provided, else of template-file path string (L53–58).
2. Cache check at `dataset/template-cache/document_template_<sha>.pkl` (L59–62). Hit → return tuple, skip all crews.
3. Template source selection (L72–86):
   - `SRS_template == 'IEEE'` → `get_srs_IEEE_Template()` (20 chapters)
   - `SRS_template == 'Initial'` → `get_srs_Initial_Template()` (7 chapters)
   - Otherwise → run `ExtractDocumentCrew` on example markdown → produces JSON skeleton → `parse_skeleton_to_document_template` builds CHAPTER tree.
4. `DocContentCrew` → writes `doc_content.md` (per-chapter content plan).
5. `ChapterDependenceCrew` → writes `chapter_dependence.md` (Python dict literal, chapter index → deps).
6. `ArtifactPlanningCrew` → writes artifact planning (list[list[str]], chapter → artifacts).
7. Pickle 5-tuple to cache path.

**Returns**: `(document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planning)`.

### 4.2 BusinessRequirements (L2) — 2 Interrupts

`BRDevrun(project_name, Description, initial_phase='survey', execute={'all': ''}, feedback_list=[], project_id=None)` is a `while execute:` loop:

1. **First iteration** (`execute == {'all': ''}`): builds `BR_Initial_Template`, calls 6 subordinate Runs to produce the 6 individual artifacts (L139–163).
2. **Business scope review** (L165–180):
   - `multiline_input(project_id, interrupt_data={"interrupt_type":"business_review", ...})`.
   - If answer != `"no"`, `modify_agent(feedback_list, …)` returns a dict like `{"context_diagram": "…", "feature_tree": "…"}` identifying what to regenerate; loop iterates with that narrower `execute`.
3. **BRD chapter generation** (L183–212):
   - Iterates `BR_Initial_Template.SUBCHAPTERS`, calls `BRDev` once per chapter with a chapter-specific `reference` list (L185–189: `[survey,business_scope] / [survey,business_scope,feature_tree,context_diagram,event_list] / [survey,user_introduction,business_scope]`).
   - `post_process()` parses the JSON chapter output, writes to the in-memory `BusinessRequirement` doc, pickles it, rewrites `BRD.md`.
4. **BRD review** (L214–230) — same pattern: accept → return; feedback → `modify_agent` → loop.

### 4.3 RequirementElicitation (L3) — 1 Interrupt

`RequirementElicitationrun(project_name, Description, execute={'all': ''}, feedback_list=[], project_id=None)`:
- Runs `UserCaseRun` + `NFRRun` (L254–257).
- `elicitation_review` interrupt at L259.
- Feedback extends to the broader reference list including `use_case` and `non_functional_requirements` (L270).

⚠️ Lines 244–251 — a commented-out re-invocation of `BRDevrun` suggests a historical cascade design; the current code only runs Elicitation crews without re-running BR.

### 4.4 RequirementAnalysis (L4) — DAG-ordered

```python
order = topological_sort(to_artifact_DAG(artifact_planing), reverse=False)
artifact_dict = {data_dictionary, ERD, data_flow_diagram, functional_requirements, dialog_map}
for artifact in order:
    if artifact in artifact_dict:
        artifact_dict[artifact].run()
```

`to_artifact_DAG(artifact_planing)` (from [../../util/DAG.py:63](../../src/util/DAG.py#L63)):
1. Collect all artifacts across all chapter plans.
2. Fixed-point propagate transitive deps from `Artifact_Dependance_rules`.
3. Build reverse adjacency: `DAG[dep] = [dependents]`.

`topological_sort(…, reverse=False)` interprets the graph as `graph[u] = successors` (Kahn's algorithm).

### 4.5 NonStandardProcess (L5)

`NonStandardProcessrun(project_name, Description, artifact_planing)` — iterates `usage_scenario` and `state_transition_diagram` crews using `run_with_retry`. Reads prior artifacts via `get_reference()`.

### 4.6 SRS Generation (L6)

`RequirementSpecificationrun` ([main.py:24](../../src/reagent/main.py#L24)):

```python
chapter_sequence = topological_sort(chapter_dependence)  # reverse=True default
SRS = parse_skeleton_to_document_template(document_skeleton, authors='csl-gpt4.1')
SRS_example = split_markdown_by_h2(read_markdown(srs_example_path))  # H2-split example

for i, chapter in enumerate(chapter_sequence):
    SRSplaningCrew.kickoff({SRS_example[i+1], reference (metadata only), dep chapter content})
    prompt = get_SRS_planning()
    SRSev.kickoff({
      chapter structure, artifact reference (with content),
      already-generated dependency chapters, prompt, chapter_index
    })
    # post_process parses chapter JSON, writes to in-memory SRS doc, pickles, rewrites SRS.md
```

Output: `SRS.md` (renderable markdown) + `SRS.pkl` (Document object) + a per-stage `appendix` listing artifact references.

## 5. `run_with_retry` Pattern

Used pervasively to wrap crew kickoffs. Signature:

```python
run_with_retry(
    crew_callable,        # the Crew class itself (not instance)
    inputs,               # dict for kickoff
    name,                 # label for logs / SSE crew_name
    retries=5, delay=15,
    post_process_callable=None,
    post_process_params=None,
)
```

Loop (5 attempts, 15s backoff). `post_process` can parse the crew's output file and return a value; `run_with_retry` returns that value (or `None` if no post-process). On all-retries-fail, raises.

The backend wraps this in [execution.py:134](../../src/backend/services/execution.py#L134) to emit `crew_start` / `artifact_complete` / `error` SSE events.

## 6. `modify_agent` Feedback Loop

[StandardProcess.py:6](../../src/reagent/StandardProcess.py#L6). When the user provides free-form feedback at an interrupt:

1. `BRDModifyLocateCrew` reads the feedback + artifact reference list and writes `BRD_modify.md` — a JSON list of artifacts that need change.
2. `get_dependent_artifacts(re_execute) & set(reference)` — compute transitive downstream artifacts via BFS on the forward dependency graph, intersected with artifacts currently in scope.
3. `BRDModifyCrew` regenerates those artifacts with feedback injected into the prompt.
4. Returns the list; the outer `while execute:` loop re-runs the matching Runs.

## 7. Artifact Catalog

See [../references/artifacts.md](../references/artifacts.md) for the full 17-artifact table (filename, stage, dependencies).

## 8. Known Issues (pipeline)

- ⚠️ **CLI skips BRDev**: [main.py:143](../../src/reagent/main.py#L143) calls `StandardProcessrun`, but [StandardProcess.py:292](../../src/reagent/StandardProcess.py#L292) runs only `MetaAnalysis + Elicitation + Analysis` — **never `BRDevrun`**. CLI mode therefore produces no BR artifacts / no BRD. The API path in [execution.py](../../src/backend/services/execution.py) calls each phase explicitly and does include BRDev.
- ⚠️ **Mutable default args** ([StandardProcess.py:135, 235](../../src/reagent/StandardProcess.py#L135)): `feedback_list=[]`, `execute={'all': ''}` shared across calls.
- ⚠️ **`feedback` variable assignment unused** in BRDevrun (L150) — concatenates latest feedback but never passes into the artifact runs (which always get the global `feedback` literal `"本轮没有人类意见"`).
- ⚠️ **Commented CompetitiveAnalysis** ([StandardProcess.py:142](../../src/reagent/StandardProcess.py#L142)) — artifact referenced elsewhere in `get_reference()` (util/__init__.py) but the run is disabled.
- ⚠️ **SRS example path is required** even when `SRS_template='IEEE'` or `'Initial'` — `DocContentCrew` still reads the example at [StandardProcess.py:93](../../src/reagent/StandardProcess.py#L93).
