# src/reagent/StandardProcess.py — Pipeline stages 1-4 orchestration + feedback loop.
#
# Outline:
#   modify_agent(feedback, project_name, Description, reference)
#     Stage-2/3 feedback handler. Uses BRDModifyLocateCrew to identify
#     artifacts needing change, expands via get_dependent_artifacts (BFS),
#     then BRDModifyCrew regenerates them. Returns re_execute list.
#
#   MetaAnalysisrun(doc_example_path, SRS_template, project_name, Description)
#     Stage 1. SHA-256 cache lookup in dataset/template-cache/; otherwise runs
#     ExtractDocumentCrew → DocContentCrew → ChapterDependenceCrew →
#     ArtifactPlanningCrew. Returns 5-tuple (cached as pickle):
#     (document_template, document_skeleton, doc_planning,
#      chapter_dependence, artifact_planing).
#
#   BRDevrun(project_name, Description, initial_phase='survey',
#            execute={'all': ''}, feedback_list=[], project_id=None)
#     Stage 2. while execute: loop that runs 6 per-artifact crews, then
#     business_scope INTERRUPT (interrupt_type="business_review"), then
#     BRDev chapter loop + BRD INTERRUPT (interrupt_type="brd_review").
#     Feedback → modify_agent → narrower execute → re-run loop.
#
#   RequirementElicitationrun(project_name, Description,
#                              execute={'all': ''}, feedback_list=[],
#                              project_id=None)
#     Stage 3. Runs UserCaseRun + NFRRun, then INTERRUPT
#     (interrupt_type="elicitation_review"). Same feedback pattern.
#
#   RequirementAnalysisrun(project_name, Description, artifact_planing)
#     Stage 4. DAG-ordered via topological_sort(to_artifact_DAG(...)).
#     Runs datadictionary, ERD, DFD, FR, DialogMap in dependency order.
#
#   StandardProcessrun(project_name, Description, srs_example_path, SRS_template)
#     CLI convenience wrapper: MetaAnalysisrun → RequirementElicitationrun
#     → RequirementAnalysisrun.
#     ⚠ Does NOT call BRDevrun — CLI mode produces no BR artifacts.
#     The API path (backend/services/execution.py) calls each phase explicitly.
from util.util import get_store_path, emit_event
from util import *
from RequirementAnalysis import DataDictionaryCrew, ERDCrew, DataFlowDiagramCrew, FRCrew, DialogMapCrew
import hashlib
from pathlib import Path
from BusinessRequirements import *

# Known artifact types per phase. Used to filter modify_agent's output so
# only legal keys end up controlling the re-execution loop.
BR_ARTIFACT_TYPES = {
    'survey', 'context_diagram', 'event_list',
    'user_introduction', 'feature_tree', 'business_scope',
}
ELICITATION_ARTIFACT_TYPES = {
    'use_case', 'non_functional_requirements',
}


def _normalize_execute(re_execute, valid_keys: set) -> dict:
    """Coerce modify_agent's return value into a dict whose keys are limited
    to ``valid_keys``. Accepts either a dict (LLM output) or list."""
    if isinstance(re_execute, dict):
        keys = re_execute.keys()
    elif isinstance(re_execute, (list, set, tuple)):
        keys = re_execute
    else:
        keys = []
    filtered = {k: '' for k in keys if k in valid_keys}
    return filtered or {}
def modify_agent(feedback, project_name: str, Description: str,reference = ['survey', 'feature_tree', 'context_diagram', 'event_list', 'user_introduction', 'business_scope']): # 历史上的改变需要变成列表叠加
    from BusinessRequirements import BRDModifyCrew, BRDModifyLocateCrew
    inputs = {
        'feedback': '\n'.join([i for i in feedback]),
        'reference': get_reference(reference, artifact = False)
    }
    def modify_post_process():
        content = read_markdown(f"{get_store_path()}/BRD_modify.md")
        if len(content) < 3:
            raise ValueError("修改结果过短，可能是修改失败了，请检查反馈内容是否符合要求，或者调整修改的参数")
        re_execute = json.loads(read_markdown(f"{get_store_path()}/BRD_modify.md"))
        return re_execute
    try:
        re_execute = run_with_retry(
            BRDModifyLocateCrew,
            inputs=inputs,
            name=f"BRDModifyCrew",
            post_process_callable=modify_post_process,
        )
    except:
        raise FileNotFoundError("can not modify BRD.")
    reference = list(get_dependent_artifacts(re_execute) & set(reference))
    inputs = {
        'feedback': '\n'.join([i for i in feedback]),
        'Description': Description,
        'project_name': project_name,
        'reference': get_reference(reference,)
    }
    try:
        re_execute = run_with_retry(
            BRDModifyCrew,
            inputs=inputs,
            name=f"BRDModifyCrew",
            post_process_callable=modify_post_process,
        )
    except:
        raise FileNotFoundError("can not modify BRD.")
    return re_execute

def justfordebug():
    return  

def MetaAnalysisrun(doc_example_path, SRS_template = None, project_name = None, Description = None):
    from MetaAnalysis import ExtractDocumentCrew, ArtifactPlanningCrew, DocContentCrew, ChapterDependenceCrew
    def sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    if doc_example_path:
        hash_template = sha256(read_markdown(doc_example_path))
    else:
        if SRS_template == 'IEEE':
            hash_template = sha256('src/util/doc_template/BusinessRequirement/IEEE_template.py')
        elif SRS_template == 'Initial':
            hash_template = sha256('src/util/doc_template/BusinessRequirement/Initial_template.py')
    template_cache_dir = Path("dataset/template-cache")
    template_cache_dir.mkdir(parents=True, exist_ok=True)
    template_cache_file = template_cache_dir / f"document_template_{hash_template}.pkl"
    if template_cache_file.exists():
        with template_cache_file.open("rb") as f:
            (document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing) = pickle.load(f)
        return document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing
    else:
        #===================== Step 1: Document Extraction =====================
        def skeleton_post_process():
            document_skeleton = get_document_skeleton()
            document_template = parse_skeleton_to_document_template(
            skeleton_json=document_skeleton,
            authors='csl-gpt4.1'
        )
            return document_template, document_skeleton
        if SRS_template == 'IEEE':
            document_template = get_srs_IEEE_Template(authors='csl')
        elif SRS_template == 'Initial':
            document_template = get_srs_Initial_Template(authors='csl')
        else:
            document_example = read_markdown(doc_example_path)
            EDC_inputs = {
        'document_chapter': document_example,
    }
            document_template, document_skeleton = run_with_retry(
            ExtractDocumentCrew,
            inputs=EDC_inputs,
            name=f"ExtractDocumentCrew",
            post_process_callable=skeleton_post_process,
        )
        
        # ===================== Step 2: Document planning =====================
        def doc_planning_post_process():
            doc_planning = json.loads(read_markdown(f"{get_store_path()}/doc_content.md"))
            return doc_planning
        doc_planning_inputs = {
            'SRS_Document_Content': read_markdown(doc_example_path), # 忽略第一个
            }
        doc_planning = run_with_retry(
            DocContentCrew,
            inputs=doc_planning_inputs,
            name=f"DocContentCrew",
            post_process_callable=doc_planning_post_process,
        )
        # ===================== Step 3: chapter dependence =====================
        def chapter_dependence_post_process():
            chapter_dependence = json.loads(read_markdown(f"{get_store_path()}/chapter_dependence.md"))
            return chapter_dependence
        chapter_dependence_inputs = {
        'doc_planning': doc_planning_post_process(), # 忽略第一个
        }
        chapter_dependence = run_with_retry(
            ChapterDependenceCrew,
            inputs=chapter_dependence_inputs,
            name=f"ChapterDependenceCrew",
            post_process_callable=chapter_dependence_post_process,
        )
        # ===================== Step 4: Artifact Planning =====================
        def artifact_post_process():
            artifact_DAG = to_artifact_DAG(get_artifact_planing())
            assert len(chapter_dependence) == len(get_artifact_planing())
        APC_inputs = {
        # 'document_structure': document_template.get_whole_document(),
        'artifact_to_choose': get_reference(artifact = False),
        'document_structure': get_document_skeleton()
    }
        run_with_retry(
            ArtifactPlanningCrew,
            inputs=APC_inputs,
            name=f"ArtifactPlanningCrew",
            post_process_callable=artifact_post_process,
        )
        artifact_planing = get_artifact_planing()
        with template_cache_file.open("wb") as f:
            pickle.dump((document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing), f)
        return document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing


def BRDevrun(project_name: str, Description: str, initial_phase: str = 'survey', execute = {'all': ''},  feedback_list = [], project_id=None):
    
    feedback = '本轮没有人类意见'
    while execute:
        BR_Initial_Template = get_br_Initial_Template(authors='csl')
        artifact_dict = {
        'survey' : surveyRun(project_name=project_name,Description=Description, BR_Initial_Template=BR_Initial_Template),
        # 'competitive_analysis' : CompetitiveAnalysisRun(project_name=project_name),
        'context_diagram' : ContextDiagramRun(project_name=project_name,Description=Description),
        'event_list' : eventlistRun(project_name=project_name,Description=Description),
        'user_introduction' : UserIntroductionRun(project_name=project_name,Description=Description),
        'feature_tree': FeatureTreeRun(project_name=project_name,Description=Description),
        'business_scope': BusinessScopeRun(project_name=project_name,Description=Description)
    }
        if 'all' not in execute:
            feedback = f'这是用户的第{len(feedback_list)}轮反馈：{feedback_list[-1]}\n'
        if ('all' in execute and initial_phase == 'survey') or 'survey' in execute:
            artifact_dict['survey'].run(feedback,execute)
        if ('all' in execute and initial_phase == 'competitive_analysis') or 'competitive_analysis' in execute:
            artifact_dict['competitive_analysis'].run(feedback,execute)
            initial_info = get_competitive_analysis()
        if 'all' in execute or 'context_diagram' in execute:
            artifact_dict['context_diagram'].run(feedback,execute)
        if 'all' in execute or 'event_list' in execute:
            artifact_dict['event_list'].run(feedback,execute)
        if 'all' in execute or 'user_introduction' in execute:
            artifact_dict['user_introduction'].run(feedback,execute)
        if 'all' in execute or 'feature_tree' in execute:
            artifact_dict['feature_tree'].run(feedback,execute,get_survey())
        # ===================== Step 5: business scope ===================
        if 'all' in execute or 'business_scope' in execute:
            artifact_dict['business_scope'].run(feedback,execute)
        print("请查看现有的business_scope.md文档并告诉我有哪些需要改进的地方：")
        answer = multiline_input(
            project_id=project_id,
            interrupt_data={
                "interrupt_type": "business_review",
                "artifact_names": ["business_scope"],
                "message": "业务范围文档已生成，请审查并提供反馈",
                "options": ["accept", "feedback"],
            } if project_id else None,
        )
        # Control flow:
        #   "exit" -> abort this phase (return)
        #   "no"   -> no feedback, proceed to BRD generation
        #   other  -> treat as feedback text, run modify_agent and loop
        if answer.lower() == "exit":
            return
        if answer.lower() != "no":
            feedback_list.append(answer)
            emit_event(project_id, "feedback_processing",
                       phase="business_scope", comment=answer)
            execute = modify_agent(feedback_list,project_name=project_name,Description=Description)
            execute = _normalize_execute(execute, BR_ARTIFACT_TYPES)
            emit_event(project_id, "artifacts_invalidated",
                       phase="business_scope",
                       artifacts=list(execute.keys()))
            if not execute:
                # Locator returned no actionable BR artifacts; treat as a no-op
                # accept rather than re-running everything.
                break
            continue

        # ===================== Step 6: BRD Chapter Generation ===================
        BRD = get_br_Initial_Template(authors='csl')
        BRD_Reference = [
            ['survey', 'business_scope'],
            ['survey', 'business_scope', 'feature_tree', 'context_diagram', 'event_list'],
            ['survey', 'user_introduction', 'business_scope'],
        ]
        def post_process():
            chapter = read_markdown(f'{get_store_path()}/business_requirements_chapter.md')
            chapter = json.loads(chapter)
            BRD.write_file(chapter)
            with open(f"{get_store_path()}/BusinessRequirementDocument.pkl", "wb") as f:
                pickle.dump(BRD, f)
            with open(f"{get_store_path()}/BRD.md", "w", encoding="utf-8") as f:
                f.write(f"{BRD.get_whole_document()}{get_dependence_appendix(BRD_Reference)}")
            
        for i in range(len(BR_Initial_Template.SUBCHAPTERS)):
            BRD_inputs = {
                'Description': Description,
                'project_name': project_name,
                'document_format_reference': BR_Initial_Template.SUBCHAPTERS[i].get_all_content(introduction = True),
                'reference': get_reference(BRD_Reference[i]),
                'chapter_index': i + 1,
            }
            run_with_retry(BRDev, 
                        BRD_inputs, 
                        name=f"BRDev Chapter {i+1}",
                        post_process_callable=post_process)
        with open(f"{get_store_path()}/BRD.md", "w", encoding="utf-8") as f:
            f.write(f"{BRD.get_whole_document(only_show_written = True)}{get_dependence_appendix(BRD_Reference)}")

        print("请查看现有的BRD.md文档(建议着重关注2.1章)并告诉我有哪些需要改进的地方：")
        answer = multiline_input(
            project_id=project_id,
            interrupt_data={
                "interrupt_type": "brd_review",
                "artifact_names": ["BRD"],
                "message": "BRD 文档已生成，请审查并提供反馈（建议着重关注2.1章）",
                "options": ["accept", "feedback"],
            } if project_id else None,
        )
        # Same control flow as the business_scope review point.
        if answer.lower() == "exit":
            return
        if answer.lower() != "no":
            feedback_list.append(answer)
            emit_event(project_id, "feedback_processing",
                       phase="BRD", comment=answer)
            execute = modify_agent(feedback_list,project_name=project_name,Description=Description)
            execute = _normalize_execute(execute, BR_ARTIFACT_TYPES)
            emit_event(project_id, "artifacts_invalidated",
                       phase="BRD",
                       artifacts=list(execute.keys()))
            if not execute:
                return
            continue
        return
    return



def RequirementElicitationrun(project_name, Description: str, execute = {'all': ''},  feedback_list = [], project_id=None):
    from RequirementElicitation import UserCaseRun,  NFRRun
    artifact_dict = {
        'use_case' : UserCaseRun(project_name=project_name,Description=Description),
        # 'competitive_analysis' : CompetitiveAnalysisRun(project_name=project_name),
        'non_functional_requirements' : NFRRun(project_name=project_name,Description=Description),
    }
    feedback = '本轮没有人类意见'
    while execute:
        if (('all' in execute) or
            ('survey' in execute) or
            ('context_diagram' in execute) or
            ('event_list' in execute) or 
            ('user_introduction' in execute) or
            ('feature_tree' in execute)):
            pass
            # BRDevrun(project_name=project_name,Description=Description, initial_phase='survey', execute = execute, feedback_list = feedback_list)
        if 'all' not in execute:
            feedback = f'这是用户的第{len(feedback_list)}轮反馈：{feedback_list[-1]}\n'
        if 'all' in execute or 'use_case' in execute:
            artifact_dict['use_case'].run(feedback,execute)       
        if 'all' in execute or 'non_functional_requirements' in execute:
            artifact_dict['non_functional_requirements'].run(feedback,execute)    
        print("请查看现有的non_functional_requirements.md和use_case.md文档并告诉我有哪些需要改进的地方？，如果没有请直接输入no：")
        answer = multiline_input(
            project_id=project_id,
            interrupt_data={
                "interrupt_type": "elicitation_review",
                "artifact_names": ["use_case", "non_functional_requirements"],
                "message": "用例和非功能需求已生成，请审查并提供反馈",
                "options": ["accept", "feedback"],
            } if project_id else None,
        )
        # Same control flow as the BR review points.
        if answer.lower() == "exit":
            return
        if answer.lower() != "no":
            feedback_list.append(answer)
            emit_event(project_id, "feedback_processing",
                       phase="elicitation", comment=answer)
            execute = modify_agent(feedback_list, reference = ['survey', 'feature_tree', 'context_diagram', 'event_list', 'user_introduction', 'use_case', 'non_functional_requirements', 'business_scope']
                                   ,project_name=project_name,Description=Description)
            execute = _normalize_execute(execute, ELICITATION_ARTIFACT_TYPES)
            emit_event(project_id, "artifacts_invalidated",
                       phase="elicitation",
                       artifacts=list(execute.keys()))
            if not execute:
                return
            continue
        return

def RequirementAnalysisrun(project_name,Description,artifact_planing):
    from RequirementAnalysis import datadictionaryRun, DataFlowDiagramRun, FunctionRequirementRun, DialogMaprun, ERDRun
    order = topological_sort(to_artifact_DAG(artifact_planing), reverse=False)
    artifact_dict = {
        'data_dictionary' : datadictionaryRun(project_name=project_name,Description=Description),
        'ERD' : ERDRun(project_name=project_name,Description=Description),
        'data_flow_diagram' : DataFlowDiagramRun(project_name=project_name,Description=Description),
        'functional_requirements' : FunctionRequirementRun(project_name=project_name,Description=Description),
        'dialog_map' : DialogMaprun(project_name=project_name,Description=Description)
    }
    for artifact in order:
        if artifact in artifact_dict.keys():
            artifact_dict[artifact].run()
    

def StandardProcessrun(project_name, Description, srs_example_path, SRS_template):
    document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing = MetaAnalysisrun(srs_example_path, SRS_template, Description=Description, project_name=project_name)
    RequirementElicitationrun(project_name, Description=Description)
    RequirementAnalysisrun(project_name,Description,artifact_planing)
    return document_template, document_skeleton, doc_planning, chapter_dependence, artifact_planing
