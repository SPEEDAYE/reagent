# Artifact Catalogue (17 Artifacts)

> Canonical dependency rules live in [../../util/DAG.py](../../src/util/DAG.py#L4) (`Artifact_Dependance_rules`). Files are written to `experiment/{project_id}/`.

| # | Artifact | Filename | Stage | Producing crew / function | Depends on |
|---|----------|----------|-------|---------------------------|------------|
| 1 | Market Survey | `survey.md` | BR | `SurveyCrew` via `surveyRun` | — |
| 2 | Context Diagram | `draft_context_diagram.md` | BR | `ContextDiagramCrew` via `ContextDiagramRun` | survey |
| 3 | Event List | `draft_event_list.md` | BR | `EventListCrew` via `eventlistRun` | context_diagram |
| 4 | User Introduction | `user_introduction.md` | BR | `UserIntroductionCrew` via `UserIntroductionRun` | context_diagram |
| 5 | Feature Tree | `feature_tree.md` | BR | `FeatureTreeCrew` via `FeatureTreeRun` | survey |
| 6 | Business Scope | `business_scope.md` | BR | `BusinessScopeCrew` via `BusinessScopeRun` | 1–5 |
| 7 | BRD | `BRD.md` (+ `BusinessRequirementDocument.pkl`) | BR | `BRDev` (chapter-by-chapter) | 1–6 |
| 8 | Use Cases | `use_case.md` (+ `UseCase.pkl`) | Elicit | `UserCaseCrew` via `UserCaseRun` | event_list, user_introduction, context_diagram |
| 9 | Non-Functional Req | `non_functional_requirements.md` | Elicit | `NFRCrew` via `NFRRun` | BRD |
| 10 | Functional Req | `functional_requirements.md` | Analysis | `FRCrew` via `FunctionRequirementRun` | use_case |
| 11 | Data Flow Diagram | `data_flow_diagram.md` | Analysis | `DataFlowDiagramCrew` via `DataFlowDiagramRun` | context_diagram, use_case |
| 12 | ERD | `entity_relationship_diagram.md` | Analysis | `ERDCrew` via `ERDRun` | DFD, context_diagram |
| 13 | Data Dictionary | `data_dictionary.md` | Analysis | `DataDictionaryCrew` via `datadictionaryRun` | ERD |
| 14 | Dialog Map | `dialog_map.md` | Analysis | `DialogMapCrew` via `DialogMaprun` | use_case |
| 15 | State Transition | `state_transition_diagram.md` | NonStd | `STDCrew` | use_case |
| 16 | Usage Scenario | `usage_scenario.md` | NonStd | `UsageScenarioCrew` | use_case |
| 17 | **SRS** | **`SRS.md`** (+ `SRS.pkl`) | **SRS Gen** | `SRSplaningCrew` + `SRSev` (chapter-by-chapter) | **all above** |

## Intermediate Artifacts (not counted in the 17)

| File | Producer | Purpose |
|------|----------|---------|
| `document_skeleton.md` | `ExtractDocumentCrew` | JSON structure of SRS template |
| `doc_content.md` | `DocContentCrew` | Per-chapter content planning (JSON) |
| `chapter_dependence.md` | `ChapterDependenceCrew` | Chapter → dep chapters (JSON dict) |
| `srs_planning.md` | `SRSplaningCrew` | Per-chapter writing plan |
| `BRD_modify.md` | `BRDModifyLocateCrew` | Feedback → list of artifacts to regenerate |
| `business_requirements_chapter.md` | `BRDev` | One chapter of BRD before assembly |
| `software_requirements_specification_chapter.md` | `SRSev` | One chapter of SRS before assembly |

## Pickle Artifacts

| File | Contents |
|------|----------|
| `BusinessRequirementDocument.pkl` | Full `BusinessRequirement` object (Document tree) |
| `SRS.pkl` | Full `SoftwareRequirementSpecification` object |
| `UseCase.pkl` | List of `UserCase` dataclass instances |

These allow pipeline resumption without re-running LLM calls for partial results.

## Dependency Graph (simplified)

```
survey ──────────────► feature_tree ─┐
       ╲                              ├──► business_scope ──► BRD ──► non_functional_requirements
        ╲                             │
         ╲──► context_diagram ──┬─────┤                  ╲
                                │     │                   └──► use_case ──┬──► functional_requirements
                                │     │                                   ├──► dialog_map
                                ├─► event_list ──► use_case              ├──► state_transition_diagram
                                │                                         └──► usage_scenario
                                └─► user_introduction
                                                                         ╲
context_diagram ──► data_flow_diagram ──► ERD ──► data_dictionary         ╲
                                                                           ╲──► SRS (consumes all)
```
