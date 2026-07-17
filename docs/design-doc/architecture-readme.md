# REagent 1.0 - Architecture Reference

## 1. Overview

REagent 1.0 is an AI-powered **Requirements Engineering (RE) automation platform** built on the [CrewAI](https://docs.crewai.com/) multi-agent framework. It takes a natural-language project description as input and produces a complete set of RE artifacts — from market surveys and business requirement documents (BRD) to a full IEEE-style Software Requirements Specification (SRS).

```
Natural Language Description
        |
        v
  +-----------+     +-----------+     +-----------+     +----------+
  |   Meta    | --> | Business  | --> |  Require  | --> |  Require |
  | Analysis  |     | Require-  |     |  Elicit-  |     |  Analy-  |
  | (template)|     |  ments    |     |  ation    |     |   sis    |
  +-----------+     +-----------+     +-----------+     +----------+
                                                              |
                    +------------------+                      |
                    | Non-Standard     |<---------------------+
                    | Process (STD,    |
                    | Usage Scenario)  |
                    +------------------+
                              |
                              v
                    +------------------+
                    | Requirement      |
                    | Specification    |
                    | (SRS Generation) |
                    +------------------+
                              |
                              v
                  BRD.md + SRS.md + 15+ artifacts
```

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Agent Framework | CrewAI 1.6.x | Multi-agent orchestration (Agent / Task / Crew) |
| LLM | OpenAI o1 (configurable) | Core reasoning engine |
| Language | Python 3.10 - 3.13 | Backend |
| Document Parsing | pdfplumber, python-docx, openpyxl, PyMuPDF | PDF/Word/Excel extraction |
| Vector DB | ChromaDB, LanceDB | Semantic search / knowledge base |
| Validation | Pydantic, jsonschema, json_repair | Output format validation |
| Caching | diskcache, pickle | Artifact persistence / template caching |
| Web (reserved) | Starlette + Uvicorn | Future API layer (not yet exposed) |
| Package Manager | uv | Fast dependency resolution |

---

## 3. Project Structure

```
reagent1.0_UI/
|
|-- src/reagent/                    # Core application source
|   |-- main.py                     # CLI entry point, argument parsing
|   |-- StandardProcess.py          # Main pipeline orchestration
|   |-- NonStandardProcess.py       # Supplementary artifact generation
|   |-- BusinessRequirements.py     # BR elicitation crews (survey, feature tree, etc.)
|   |-- RequirementElicitation.py   # Use case & NFR crews
|   |-- RequirementAnalysis.py      # Data/functional analysis crews (DFD, ERD, etc.)
|   |-- RequirementSpecification.py # SRS chapter-by-chapter generation
|   |-- RequirementExtraction.py    # PDF/Office document parser
|   |-- MetaAnalysis.py             # Document template analysis & planning
|   |-- config/
|   |   |-- agents.yaml             # Agent role/goal/backstory definitions
|   |   |-- tasks.yaml              # Task prompt templates (Chinese, 81KB)
|   |   |-- tasks_eng.yaml          # Task prompt templates (English)
|   |-- tools/
|       |-- custom_tool.py          # Custom CrewAI tool definitions
|
|-- util/                           # Shared utilities & models
|   |-- __init__.py                 # Re-exports + run_with_retry() + get_reference()
|   |-- util.py                     # File I/O helpers, artifact getters
|   |-- DAG.py                      # Artifact dependency graph & topological sort
|   |-- Artifacts.py                # Artifact-to-appendix mapping
|   |-- SoftwareManager.py          # CrewAI base class (LLM config, shared agent)
|   |-- user_case.py                # UserCase Pydantic model
|   |-- validate_format.py          # JSON schema validation rules
|   |-- doc_template/               # Document template system
|       |-- chapter.py              # CHAPTER / PARAGRAPH data classes
|       |-- document.py             # Document tree (parse / render markdown)
|       |-- document_example.md     # SRS reference template (58KB)
|       |-- BusinessRequirement/
|       |   |-- BR.py               # BR document class
|       |   |-- Initial_template.py # BR initial template factory
|       |-- SoftwareRequirementSpecification/
|           |-- SRS.py              # SRS document class
|           |-- IEEE_template.py    # IEEE 830 template factory
|           |-- Initial_template.py # Initial SRS template factory
|
|-- experiment/                         # Generated artifacts (markdown + pickle)
|-- dataset/requirements/                    # Input project description files
|-- data/                           # Input data (PDFs, Word docs)
|-- dataset/template-cache/                       # Cached parsed templates (pickle)
|-- knowledge/                      # Knowledge base directory
|-- start.sh                        # Quick-start shell script
|-- pyproject.toml                  # Project metadata & CLI entry points
|-- requirements.txt                # pip dependencies
```

---

## 4. Architecture Layers

### Layer 1: CLI Entry (`main.py`)

The single entry point. Parses CLI arguments and drives the three-step pipeline:

```python
def main():
    # Optional: Extract requirements from PDF/Word documents
    RequirementsExtractionRun(...)

    # Step 1: Standard Process (Meta-Analysis + BR + Elicitation + Analysis)
    StandardProcessrun(project_name, Description, srs_example_path, SRS_template)

    # Step 2: Non-Standard Process (Usage Scenarios, State Transition Diagrams)
    NonStandardProcessrun(project_name, Description, artifact_planing)

    # Step 3: SRS Chapter-by-Chapter Generation
    RequirementSpecificationrun(document_template, ..., srs_example_path)
```

**CLI Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--project_name` | No | "自动化软件源代码审查平台" | Project name |
| `--description_file` | **Yes** | - | Path to project description text file |
| `--data_path` | No | None | Folder with PDF/Word documents for extraction |
| `--srs_example_path` | No | `src/util/doc_template/document_example.md` | SRS template reference |
| `--srs_template` | No | None | Template type: `IEEE` or `Initial` |

### Layer 2: Process Orchestration (`StandardProcess.py`, `NonStandardProcess.py`)

Coordinates the execution of specialized Crew groups across 5 phases:

```
StandardProcessrun()
  |-- MetaAnalysisrun()            # Phase 1: Template structure extraction
  |-- BRDevrun()                   # Phase 2: Business Requirements (with feedback loop)
  |-- RequirementElicitationrun()  # Phase 3: Use Cases + NFR (with feedback loop)
  |-- RequirementAnalysisrun()     # Phase 4: Data & Functional artifacts

NonStandardProcessrun()            # Phase 4b: Supplementary artifacts
  |-- UsageScenariorun()
  |-- StateTransitionDiagramrun()
```

Key design decisions:
- **Feedback loops**: Phases 2 and 3 pause for human feedback via `multiline_input()`, enabling iterative refinement
- **Change propagation**: When the user provides feedback, `modify_agent()` identifies affected artifacts via the DAG and re-executes only what is needed
- **Topological ordering**: Phase 4 uses `topological_sort()` to determine correct execution order based on artifact dependencies

### Layer 3: CrewAI Task Execution (Business/Elicitation/Analysis modules)

Each RE activity is implemented as a **CrewAI Crew** — a combination of Agent(s) and Task(s).

**Inheritance hierarchy:**

```
SoftwareManagerCrew              # Base: LLM config, shared Agent, crew(), lifecycle hooks
  |
  +-- BusinessRequirementsDevCrew  # Adds WebsiteSearchTool to agent
  |     |-- SurveyCrew
  |     |-- FeatureTreeDev
  |     |-- DraftContentDiagramCrew
  |     |-- DraftEventListCrew
  |     |-- UserIntroductionDev
  |     |-- BusinessScopeDev
  |     |-- BRDev
  |     |-- BRDModifyCrew / BRDModifyLocateCrew
  |     +-- CompetitiveAnalysisCrew
  |
  +-- (RequirementElicitation crews)
  |     |-- UserCaseCrew
  |     |-- NFRCrew
  |     +-- UsageScenarioCrew
  |
  +-- (RequirementAnalysis crews)
  |     |-- DataFlowDiagramCrew
  |     |-- ERDCrew
  |     |-- DataDictionaryCrew
  |     |-- DialogMapCrew
  |     |-- FRCrew
  |     +-- STDCrew
  |
  +-- (MetaAnalysis crews)
  |     |-- ExtractDocumentCrew
  |     |-- DocContentCrew
  |     |-- ChapterDependenceCrew
  |     +-- ArtifactPlanningCrew
  |
  +-- (RequirementSpecification crews)
        |-- SRSplaningCrew
        +-- SRSev
```

**Runner pattern**: Each Crew has a corresponding `*Run` class (e.g., `surveyRun`, `ContextDiagramRun`) that:
1. Assembles input dictionaries with references to prior artifacts
2. Calls `run_with_retry()` with the Crew and a post-process validator
3. Handles feedback injection for iterative rounds

### Layer 4: Artifact Dependency Graph (`DAG.py`)

The system manages **16 artifact types** with explicit dependency relationships:

```
survey ─────────────────────────────────────────────────────────┐
  |                                                              |
  +-> context_diagram ──+-> event_list ─────────────────────┐   |
  |                     +-> user_introduction ──────────┐   |   |
  |                     |                               |   |   |
  +-> feature_tree ─────+-> business_scope ─────────────+---+---+--> BRD
                        |                               |
                        +-> use_case ──+-> functional_requirements
                             |         +-> data_flow_diagram -> ERD -> data_dictionary
                             |         +-> state_transition_diagram
                             |         +-> dialog_map
                             |         +-> usage_scenario
                             |
                             +-> non_functional_requirements (via BRD)
```

**Core algorithms in `DAG.py`:**

| Function | Purpose |
|----------|---------|
| `topological_sort(graph)` | Kahn's algorithm; determines safe execution order |
| `get_dependent_artifacts(changed)` | BFS on forward-impact graph; finds all artifacts to regenerate |
| `to_artifact_DAG(artifact_planning)` | Builds DAG from planning output; auto-adds transitive dependencies |
| `detect_dependency_cycles(rules)` | DFS cycle detection; guards against invalid configurations |

### Layer 5: Document Template System (`src/util/doc_template/`)

A tree-based document model supporting up to 4-level nesting:

```
Document (title, author, date)
  +-- CHAPTER (level 1: "1. Introduction")
  |     +-- CHAPTER (level 2: "1.1 Purpose")
  |     |     +-- CHAPTER (level 3: "1.1.1 Scope")
  |     |           +-- CHAPTER (level 4: "1.1.1.1 Details")
  |     +-- CHAPTER (level 2: "1.2 Definitions")
  +-- CHAPTER (level 1: "2. Overall Description")
        ...
```

**Key operations:**
- `parse_skeleton_to_document_template()`: JSON skeleton -> Document tree
- `Document.write_file(chapter_json)`: Populates a chapter from LLM output
- `Document.get_whole_document()`: Renders full markdown output

**Template factories:**
- `Create_BR_Initial_Template()` -> 3-chapter BRD (Background & Goals, Scope, User Classes)
- `Create_SRS_IEEE_Template()` -> IEEE 830 standard SRS structure
- `Create_SRS_Initial_Template()` -> Simplified SRS structure

---

## 5. Execution Pipeline (Detailed)

### Phase 1: Meta-Analysis

**Goal**: Extract and plan the document structure from the SRS template.

```
Input: SRS example template (markdown)
  |
  +-> ExtractDocumentCrew: Parse template into JSON skeleton
  +-> DocContentCrew: Analyze content structure per chapter
  +-> ChapterDependenceCrew: Determine inter-chapter dependencies
  +-> ArtifactPlanningCrew: Map RE artifacts to SRS chapters
  |
Output: document_template, document_skeleton, doc_planning,
        chapter_dependence, artifact_planing
```

**Caching**: Results are pickled with a SHA-256 hash of the template file. If the same template is used again, the cached result is returned immediately.

### Phase 2: Business Requirements Development

**Goal**: Generate all business-level requirement artifacts with human-in-the-loop feedback.

```
Loop until user approves:
  |
  +-> SurveyCrew: Research existing solutions in the market
  +-> DraftContentDiagramCrew: Define system boundaries (context diagram)
  +-> DraftEventListCrew: Identify external events/triggers
  +-> UserIntroductionDev: Define user personas and classifications
  +-> FeatureTreeDev: Build hierarchical feature decomposition
  +-> BusinessScopeDev: Document business goals and constraints
  |
  +-- User reviews business_scope.md -> provides feedback or approves
  |   (if feedback: BRDModifyLocateCrew identifies changes,
  |    propagates through DAG, re-executes affected artifacts)
  |
  +-> BRDev: Generate BRD chapter by chapter (3 chapters)
  |
  +-- User reviews BRD.md -> provides feedback or approves
```

### Phase 3: Requirement Elicitation

**Goal**: Derive structured use cases and non-functional requirements.

```
Loop until user approves:
  |
  +-> UserCaseCrew: Generate structured use cases
  |   (with preconditions, main/alt/exception flows, etc.)
  +-> NFRCrew: Define performance, security, reliability requirements
  |
  +-- User reviews use_case.md + non_functional_requirements.md
```

### Phase 4: Requirement Analysis

**Goal**: Produce data and functional design artifacts in dependency order.

```
topological_sort(artifact_DAG) -> execution order
  |
  +-> DataFlowDiagramCrew (depends on: context_diagram, use_case)
  +-> ERDCrew (depends on: data_flow_diagram, context_diagram)
  +-> DataDictionaryCrew (depends on: ERD)
  +-> DialogMapCrew (depends on: use_case)
  +-> FRCrew (depends on: use_case)
```

### Phase 4b: Non-Standard Process

**Goal**: Generate supplementary artifacts not part of the standard flow.

```
+-> UsageScenarioRun (depends on: use_case)
+-> StateTransitionDiagramRun (depends on: use_case)
```

### Phase 5: SRS Generation

**Goal**: Produce the final Software Requirements Specification, chapter by chapter.

```
For each chapter in topological order:
  |
  +-> SRSplaningCrew: Plan chapter content based on:
  |   - SRS example for that chapter
  |   - Referenced RE artifacts
  |   - Previously written dependent chapters
  |
  +-> SRSev: Generate chapter content
  |   - Uses the planning prompt
  |   - References all mapped artifacts
  |   - Includes content from dependency chapters
  |
  +-> Post-process: Write chapter to Document tree, save SRS.pkl + SRS.md
```

---

## 6. Key Mechanisms

### 6.1 Retry with Validation (`run_with_retry`)

All Crew executions go through `run_with_retry()` in `util/__init__.py`:

```python
run_with_retry(
    crew_callable,          # Crew class (instantiated inside)
    inputs,                 # Dict of template variables for tasks.yaml
    name,                   # Display name for logging
    retries=5,              # Max attempts
    delay=15,               # Seconds between retries
    post_process_callable,  # Optional validator/transformer
)
```

Flow:
1. Instantiate the Crew and call `crew().kickoff(inputs=inputs)`
2. If `post_process_callable` is provided, call it to validate/transform output
3. If either step raises an exception, wait `delay` seconds and retry
4. After `retries` failures, raise the last exception

### 6.2 Reference Assembly (`get_reference`)

`get_reference()` in `util/__init__.py` builds a structured prompt string containing all referenced artifacts. For each artifact type:
1. Appends a **description** explaining what the artifact is and how to use it
2. If `artifact=True`, appends the **actual content** from the output file

This mechanism allows the LLM to understand both the semantics and actual content of referenced artifacts.

### 6.3 Feedback & Change Propagation

When a user provides feedback:
1. `BRDModifyLocateCrew` analyzes the feedback to identify which artifacts need changes
2. `get_dependent_artifacts()` uses BFS on the forward-impact graph to find all transitively affected artifacts
3. The `execute` dictionary is updated with only the affected artifact names
4. The pipeline re-enters the generation loop, skipping unaffected artifacts

### 6.4 Template Caching

`MetaAnalysisrun()` caches its results using:
- Key: SHA-256 hash of the template file content
- Storage: `dataset/template-cache/document_template_{hash}.pkl`
- Contains: `(document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing)`

This avoids re-analyzing the same template across runs.

---

## 7. Data Flow

### Input

| Source | Format | Used By |
|--------|--------|---------|
| `--description_file` | Plain text (UTF-8) | All Crews via `{Description}` template variable |
| `--data_path` | PDF / Word / Excel files | `RequirementExtraction.py` |
| `--srs_example_path` | Markdown | `MetaAnalysis`, `RequirementSpecification` |
| `config/tasks.yaml` | YAML with template variables | CrewAI task definitions |
| `config/agents.yaml` | YAML | CrewAI agent definitions |

### Intermediate Artifacts (written to `experiment/`)

| File | Artifact Type | Generated By |
|------|--------------|-------------|
| `survey.md` | Market survey | SurveyCrew |
| `feature_tree.md` | Feature hierarchy | FeatureTreeDev |
| `draft_context_diagram.md` | System boundary | DraftContentDiagramCrew |
| `draft_event_list.md` | External events | DraftEventListCrew |
| `user_introduction.md` | User personas | UserIntroductionDev |
| `business_scope.md` | Business scope | BusinessScopeDev |
| `UseCase.pkl` | Structured use cases | UserCaseCrew |
| `non_functional_requirements.md` | NFR | NFRCrew |
| `data_flow_diagram.md` | DFD (Mermaid) | DataFlowDiagramCrew |
| `entity_relationship_diagram.md` | ERD | ERDCrew |
| `data_dictionary.md` | Data dictionary | DataDictionaryCrew |
| `dialog_map.md` | UI dialog flow | DialogMapCrew |
| `functional_requirements.md` | Functional spec | FRCrew |
| `state_transition_diagram.md` | State diagram | STDCrew |
| `usage_scenario.md` | Usage scenarios | UsageScenarioCrew |

### Final Output

| File | Description | Typical Size |
|------|------------|-------------|
| `BRD.md` | Business Requirement Document (3 chapters + appendix) | ~96 KB |
| `SRS.md` | Software Requirements Specification (full document + appendix) | ~292 KB |
| `BusinessRequirementDocument.pkl` | Serialized BRD Document object | Variable |
| `SRS.pkl` | Serialized SRS Document object | Variable |

---

## 8. Configuration

### Environment Variables (`.env`)

```bash
OPENAI_MODEL=o1              # LLM model identifier
OPENAI_KEY=sk-...            # API key
OPENAI_BASE_URL=https://...  # Optional custom endpoint
```

### Agent Configuration (`config/agents.yaml`)

Defines a single shared agent used by all Crews:

```yaml
SoftwareManager:
  role: "Software manager"
  goal: "Complete the requirements engineering lifecycle"
  backstory: "10+ years of software project management experience..."
```

### Task Configuration (`config/tasks.yaml`)

81KB of Chinese-language task prompt templates. Each task uses template variables:

```yaml
survey_task:
  description: >
    项目名称：{project_name}
    项目描述：{Description}
    用户反馈：{feedback}
    ...
  expected_output: >
    Structured survey report in markdown format
```

An English equivalent is available in `tasks_eng.yaml` (26KB).

---

## 9. Extension Points

| Extension | How |
|-----------|-----|
| Add a new artifact type | 1. Add entry to `Artifact_Dependance_rules` in `DAG.py`; 2. Create Crew class; 3. Add task in `tasks.yaml`; 4. Add `*Run` class; 5. Register in process orchestrator |
| Change LLM model | Update `OPENAI_MODEL` in `.env` (or pass any OpenAI-compatible model) |
| Add a new document template | Create a factory function in `src/util/doc_template/` following the pattern of `IEEE_template.py` |
| Custom tools for agents | Add to `src/reagent/tools/custom_tool.py` and reference in agent definition |
| Add new SRS chapters | Extend the template in `document_example.md` or modify the template factory |
| Expose as REST API | Starlette + Uvicorn dependencies are already installed; wrap `main()` pipeline behind HTTP endpoints |

---

## 10. Quick Start

```bash
# Install dependencies
uv pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your OPENAI_KEY and OPENAI_MODEL

# Run with default example
bash start.sh

# Or run directly
python src/reagent/main.py \
  --project_name "My Project" \
  --description_file "dataset/requirements/my_project.txt" \
  --srs_example_path "src/util/doc_template/document_example.md"
```

### CLI Entry Points (via pyproject.toml)

```bash
reagent          # Main pipeline
run_crew         # Alias for main
train            # Training mode
replay           # Replay mode
test             # Test mode
run_with_trigger # Trigger-based execution
```
