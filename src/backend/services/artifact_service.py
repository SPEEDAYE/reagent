# backend/services/artifact_service.py — File-system backed artifact CRUD.
#
# Outline:
#   ARTIFACT_META            17 artifact key → (display_name_zh, filename)
#   ARTIFACT_STAGE           artifact key → owning pipeline stage
#   _get_dep_rules()         lazy import of util.DAG.Artifact_Dependance_rules
#   _get_dependents()        inverted dependency index (cached)
#   _read_file(path)         UTF-8 read, "" if missing
#
#   ArtifactService
#     _project_dir(pid)      experiment/{pid}/
#     list_all(pid)          walk 17 artifacts; merge status + preview + deps
#     get_content(pid, name) full markdown + deps for a single artifact
#     get_dag(pid)           nodes+edges payload for frontend DAG viz
import os
from backend.config import settings

# Artifact name -> (display_name, filename)
ARTIFACT_META: dict[str, tuple[str, str]] = {
    "survey":                       ("市场调研报告",           "survey.md"),
    "context_diagram":              ("上下文图",               "draft_context_diagram.md"),
    "event_list":                   ("事件列表",               "draft_event_list.md"),
    "user_introduction":            ("用户介绍",               "user_introduction.md"),
    "feature_tree":                 ("功能树",                 "feature_tree.md"),
    "business_scope":               ("业务范围",               "business_scope.md"),
    "BRD":                          ("业务需求文档",           "BRD.md"),
    "use_case":                     ("用例",                   "use_case.md"),
    "non_functional_requirements":  ("非功能需求",             "non_functional_requirements.md"),
    "functional_requirements":      ("功能需求",               "functional_requirements.md"),
    "data_flow_diagram":            ("数据流图",               "data_flow_diagram.md"),
    "ERD":                          ("实体关系图",             "entity_relationship_diagram.md"),
    "data_dictionary":              ("数据字典",               "data_dictionary.md"),
    "dialog_map":                   ("对话图",                 "dialog_map.md"),
    "state_transition_diagram":     ("状态转换图",             "state_transition_diagram.md"),
    "usage_scenario":               ("使用场景",               "usage_scenario.md"),
    "SRS":                          ("软件需求规格说明书",     "SRS.md"),
}

# Stage mapping
ARTIFACT_STAGE: dict[str, str] = {
    "survey": "business_requirements",
    "context_diagram": "business_requirements",
    "event_list": "business_requirements",
    "user_introduction": "business_requirements",
    "feature_tree": "business_requirements",
    "business_scope": "business_requirements",
    "BRD": "business_requirements",
    "use_case": "requirement_elicitation",
    "non_functional_requirements": "requirement_elicitation",
    "functional_requirements": "requirement_analysis",
    "data_flow_diagram": "requirement_analysis",
    "ERD": "requirement_analysis",
    "data_dictionary": "requirement_analysis",
    "dialog_map": "requirement_analysis",
    "state_transition_diagram": "non_standard",
    "usage_scenario": "non_standard",
    "SRS": "srs_generation",
}

# Import dependency rules lazily to avoid circular imports
_dep_rules = None
_dependents_cache = None


def _get_dep_rules():
    global _dep_rules
    if _dep_rules is None:
        from util.DAG import Artifact_Dependance_rules
        _dep_rules = Artifact_Dependance_rules
    return _dep_rules


def _get_dependents():
    global _dependents_cache
    if _dependents_cache is None:
        rules = _get_dep_rules()
        _dependents_cache = {name: [] for name in ARTIFACT_META}
        for name, deps in rules.items():
            for dep in deps:
                if dep in _dependents_cache:
                    _dependents_cache[dep].append(name)
    return _dependents_cache


def _read_file(filepath: str) -> str:
    if not os.path.isfile(filepath):
        return ""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


class ArtifactService:
    def __init__(self, output_dir: str | None = None):
        self.output_dir = output_dir or settings.OUTPUT_DIR

    def _project_dir(self, project_id: str) -> str:
        """Return per-project output directory: experiment/{project_id}/"""
        return os.path.join(self.output_dir, project_id)

    def list_all(self, project_id: str) -> dict:
        rules = _get_dep_rules()
        dependents = _get_dependents()
        artifacts = []
        pdir = self._project_dir(project_id)
        for name, (display, filename) in ARTIFACT_META.items():
            filepath = os.path.join(pdir, filename)
            content = _read_file(filepath)
            status = "completed" if content else "pending"
            artifacts.append({
                "artifact_name": name,
                "display_name": display,
                "filename": filename,
                "stage": ARTIFACT_STAGE.get(name, ""),
                "status": status,
                "content_preview": content[:200] if content else "",
                "dependencies": rules.get(name, []),
                "dependents": dependents.get(name, []),
            })
        completed = sum(1 for a in artifacts if a["status"] == "completed")
        return {
            "project_id": project_id,
            "artifacts": artifacts,
            "total": len(artifacts),
            "completed": completed,
            "in_progress": 0,
            "pending": len(artifacts) - completed,
        }

    def get_content(self, project_id: str, artifact_name: str) -> dict:
        meta = ARTIFACT_META.get(artifact_name)
        if not meta:
            return {"error": f"Unknown artifact: {artifact_name}"}
        display, filename = meta
        filepath = os.path.join(self._project_dir(project_id), filename)
        content = _read_file(filepath)
        rules = _get_dep_rules()
        dependents = _get_dependents()
        return {
            "artifact_name": artifact_name,
            "display_name": display,
            "status": "completed" if content else "pending",
            "content": content,
            "dependencies": rules.get(artifact_name, []),
            "dependents": dependents.get(artifact_name, []),
        }

    def get_dag(self, project_id: str) -> dict:
        """Return nodes + edges for frontend DAG rendering."""
        rules = _get_dep_rules()
        pdir = self._project_dir(project_id)
        nodes = []
        edges = []
        for name, (display, filename) in ARTIFACT_META.items():
            filepath = os.path.join(pdir, filename)
            status = "completed" if os.path.isfile(filepath) and os.path.getsize(filepath) > 0 else "pending"
            nodes.append({
                "id": name,
                "label": display,
                "status": status,
                "stage": ARTIFACT_STAGE.get(name, ""),
            })
            for dep in rules.get(name, []):
                edges.append({"from": dep, "to": name})
        return {"nodes": nodes, "edges": edges}
