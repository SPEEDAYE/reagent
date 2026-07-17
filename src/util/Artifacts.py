# util/Artifacts.py — Artifact appendix renderer.
#
# get_dependence_appendix(dependence_list) → str
#   Takes list[list[str]] (per-chapter artifact refs), dedupes, emits
#   "# 附录：依赖项说明" markdown section pointing to each artifact's .md.
def get_dependence_appendix(dependence_list: list):
    all_artifacts = set()
    for line in dependence_list:
        for artifact in line:
            all_artifacts.add(artifact)
    result = ''
    if len(all_artifacts) >= 0:
        result += f'# 附录：依赖项说明\n'
    for artifact in all_artifacts: 
        if artifact == 'BRD':
            result += f"- 业务需求文档（BRD）参见 BRD.md\n"
        elif artifact == 'context_diagram':
            result += f"- 上下文图参见 draft_context_diagram.md\n"
        elif artifact == 'user_introduction':
            result += f"- 用户介绍参见 user_introduction.md\n"
        elif artifact == 'event_list':
            result += f"- 外部事件列表参见 event_list.md\n"
        elif artifact == 'ERD':
            result += f"- 实体关系表参见 entity_relationship_diagram.md\n"
        elif artifact == 'competitive_analysis': 
            result += f"- 竞品分析参见 competitive_analysis.md\n"
        elif artifact == 'user_case':
            result += f"- 用户用例说明参见 user_case.md\n"
        elif artifact == 'dialog_map':
            result += f"- 对话图参见 dialog_map.md\n"
        elif artifact == 'data_flow_diagram':
            result += f"- 数据流图参见 data_flow_diagram.md\n"
        elif artifact == 'data_dictionary':
            result += f"- 数据字典参见 data_dictionary.md\n"
        elif artifact == 'survey':
            result += f"- 现有解决方案调研参见 survey.md\n"
        elif artifact == 'state_transition_diagram':
            result += f"- 状态转换图参见 state_transition_diagram.md\n"
        elif artifact == 'feature_tree':
            result += f"- 系统特性树参见 feature_tree.md\n"
        elif artifact == 'functional_requirements':
            result += f"- 功能需求参见 functional_requirements.md\n"
        elif artifact == 'non_functional_requirements':
            result += f"- 非功能性需求参见 non_functional_requirements.md\n"
        elif artifact == 'usage_scenario':
            result += f"- 使用场景参见 usage_scenario.md\n"
        elif artifact == 'feature_tree':
            result += f"- 系统特性树参见 feature_tree.md\n"
    return result
