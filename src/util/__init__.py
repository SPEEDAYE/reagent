# util/__init__.py — Public util API facade.
#
# Outline:
#   Re-exports util.util, util.DAG, util.Artifacts, util.validate_format
#   plus UserCase class.
#   get_br_Initial_Template(authors)    → 3-chapter BR template
#   get_srs_IEEE_Template(authors)      → 20-chapter IEEE 830 SRS template
#   get_srs_Initial_Template(authors)   → 7-chapter basic SRS template
#   run_with_retry(crew_callable, inputs, name, retries=5, delay=15,
#                  post_process_callable=None, post_process_params=None)
#       Executes crew_callable().crew().kickoff(inputs) with retry.
#       On success, optionally runs post_process; returns post_process's
#       non-None result (else None). Raises after retries exhausted.
#   get_reference(reference=None, artifact=True) → str
#       Builds Chinese artifact-context prompt. artifact=True inlines content.
from util.util import *
from util.DAG import *
from util.Artifacts import *
from util.validate_format import *
from util.user_case import UserCase
from util.doc_template.BusinessRequirement.Initial_template import Create_BR_Initial_Template
from util.doc_template.SoftwareRequirementSpecification.IEEE_template import Create_SRS_IEEE_Template
from util.doc_template.SoftwareRequirementSpecification.Initial_template import Create_SRS_Initial_Template 
from util.doc_template.document import parse_skeleton_to_document_template
def get_br_Initial_Template(authors: str = 'csl'):
    return Create_BR_Initial_Template(authors=authors)

def get_srs_IEEE_Template(authors: str = 'csl'):
    return Create_SRS_IEEE_Template(authors=authors)

def get_srs_Initial_Template(authors: str = 'csl'):
    return Create_SRS_Initial_Template(authors=authors)

import ctypes
import gc
import os
import time


def _progress(stage: str, message: str, *, current: int | None = None, total: int | None = None) -> None:
    try:
        from reagent.progress import TerminalProgress
        TerminalProgress.from_env().update(stage, message, current=current, total=total)
    except Exception:
        prefix = f"[{stage}]"
        detail = f" ({current}/{total})" if current is not None and total is not None else ""
        print(f"{prefix}{detail} {message}")


def _release_crew_memory() -> None:
    """Release cyclic Crew objects and return free glibc pages to Linux."""
    gc.collect()
    if os.name != "posix":
        return
    try:
        libc = ctypes.CDLL(None)
        malloc_trim = getattr(libc, "malloc_trim", None)
        if malloc_trim is not None:
            malloc_trim(0)
    except (AttributeError, OSError):
        # malloc_trim is a glibc optimisation; other POSIX runtimes can skip it.
        pass


def run_with_retry(
    crew_callable,
    inputs,
    name,
    retries=5,
    delay=15,
    post_process_callable=None,
    post_process_params=None,
):
    last_error = None

    for attempt in range(1, retries + 1):
        crew_instance = None
        crew_runner = None
        try:
            _progress("crew_attempt", name, current=attempt, total=retries)
            crew_instance = crew_callable()
            crew_runner = crew_instance.crew()
            crew_runner.kickoff(inputs=inputs)

            _progress("crew_success", name)

            # === 核心改造点 ===
            if post_process_callable:
                result = (
                    post_process_callable(post_process_params)
                    if post_process_params is not None
                    else post_process_callable()
                )

                # 只有 post_process 有“非 None 输出”才 return
                if result is not None:
                    return result

            return  # 无 post_process 或 post_process 无输出 → 不返回任何值

        except Exception as e:
            last_error = e
            _progress("crew_error", f"{name}: {e}", current=attempt, total=retries)

            if attempt < retries:
                time.sleep(delay)
            else:
                raise Exception(
                    f"[{name}] Failed after {retries} retries: {last_error}"
                )
        finally:
            # CrewAI objects contain agents, tasks, callbacks and HTTP clients.
            # Explicitly break the local reference chain between chapter calls;
            # otherwise long SRS runs can retain enough native heap for the
            # operating system to terminate the pipeline worker.
            crew_runner = None
            crew_instance = None
            _release_crew_memory()


# def get_reference(reference: list):
#     result = 'here is your reference information:\n'
#     if "competitive_analysis" in reference:
#         competitive_analysis = get_competitive_analysis()
#         result += f"Here is the competitive analysis section in the appendix:\n{competitive_analysis}\n"
#     if "business_process_model" in reference:
#         business_process_model = get_business_process()
#         result += f"Here is the Business Process Model section in the appendix:\n{business_process_model}\n"
#     if "state_transition_diagram" in reference:
#         state_transition_diagram = get_state_transition_diagram()
#         result += f"Here is the State Transition Diagram section in the appendix:\n{state_transition_diagram}\n"
#     if "feature_tree" in reference:
#         feature_tree = get_feature_tree()
#         result += f"Here is the Feature Tree of the system section in the appendix:\n{feature_tree}\n"
#     if "context_diagram" in reference:
#         context_diagram = get_context_diagram()
#         result += f"Here is the Context Diagram section in the appendix:\n{context_diagram}\n"
#     if "user_introduction" in reference:
#         user_introduction = get_user_introduction()
#         result += f"Here is the User Introduction section in the appendix:\n{user_introduction}\n"
#     if "data_flow_diagram" in reference:
#         data_flow_diagram = get_data_flow_diagram()
#         result += f"Here is the Data Flow Diagram section in the appendix:\n{data_flow_diagram}\n"
#     if "data_dictionary" in reference:
#         data_dictionary = get_data_dictionary()
#         result += f"Here is the Data Dictionary section in the appendix:\n{data_dictionary}\n"
#     if "dialog_map" in reference:
#         dialog_map = get_dialog_map()
#         result += f"Here is the Dialog Map section in the appendix:\n{dialog_map}\n"
#     if "BRD" in reference:
#         BRD = get_BRD().get_whole_document()
#         result += f"Here is the Business Requirement Document section in the appendix:\n{BRD}\n"
#     if "user_case" in reference:
#         UCL = get_user_case()
#         result += f"Here is the User Case Descriptions section in the appendix:\n{UCL}\n"
#     if "survey" in reference:
#         survey = get_survey()
#         result += f"Here is the Survey about existing solutions section in the appendix:\n{survey}\n"
#     if "non_functional_requirements" in reference:
#         NFR = get_non_functional_requirements()
#         result += f"Here is the Non-Functional Requirements section in the appendix:\n{NFR}\n"
#     return result

def get_reference(reference = None, artifact = True):
    if reference is None:
        reference = ['event_list', "state_transition_diagram", "feature_tree", "context_diagram", 'user_introduction', 
                     "data_flow_diagram", "data_dictionary", "dialog_map", "BRD", "use_case", 
                     "survey", "non_functional_requirements", 'functional_requirements', 'ERD', 'usage_scenario',]
    result = '以下是你的参考信息：\n'
    if reference == []:
        result += '本节没有参考的需求工程工件。'
    if "competitive_analysis" in reference:
        competitive_analysis = get_competitive_analysis()
        result += f"以下是附录中的**竞品分析**部分：\n{competitive_analysis}\n"
    if "business_scope" in reference:
        result += """
        你的可参考**需求工件**包括**业务范围文档**，这是介绍。
        **外部事件列表**包含了业务目标、成功指标、软件项目主要功能、软件项目功能限制与排除、利益相关者画像"""
        if artifact:
            business_scope = get_business_scope()
            result += f"以下是附录中的**业务范围文档**部分：\n{business_scope}\n"
    if "event_list" in reference:
        result += """
        你的可参考**需求工件**包括**外部事件列表**，这是介绍。
        **外部事件列表**包含了系统中外部实体与系统互动的可能事件。用于表述软件系统的范围"""
        if artifact:
            event_list = get_event_list()
            result += f"""以下是附录中的**外部事件列表**部分：\n{event_list}\n"""
    
    if 'functional_requirements' in reference:
        result += """
    你的可参考**需求工件**包括**功能需求**，
    **功能需求**明确描述系统应该执行的具体功能和行为，
    您可以从系统所做的事情或用户可以做的事情的角度来编写功能要求。
    **功能需求**可以分为从用户角度以及从系统角度出发的功能需求。"""
        if artifact:
            functional_requirements = get_functional_requirements()
            result += f"以下是附录中的**功能需求**部分：\n{functional_requirements}\n"

    if "state_transition_diagram" in reference:
        result += (
        """
    你的可参考**需求工件**包括**状态转换图**，
    **状态转换图**提供了对象或系统状态的简洁、完整和明确的表示。状态转换图（STD）直观地显示了状态之间可能的转换。
    **状态转换图**提供了一个跨越多个用例或用户故事的高级视图，每个用例或用户故事都可能执行从一个状态到另一个状态的转换。
    它们只显示了处理过程中可能发生的状态变化，帮助开发人员理解系统的预期行为。"""
    )
        if artifact:
            state_transition_diagram = get_state_transition_diagram()
            result += (
        "以下是附录中的**状态转移图**部分：\n"
        f"{state_transition_diagram}\n"
    )

    if "feature_tree" in reference:
        result += (
        "你的可参考**需求工件**包括**系统特征树**，\n"
        """**系统特征树**是对产品特征的视觉描述，用于表述软件系统的范围。这些特征被组织成逻辑组，将每个特征分层细分为进一步的细节级别（Beatty and Chen 2012）。
    **系统特征树**提供了为项目计划的所有特征的简明视图，使其成为向想要快速浏览项目范围的高管展示的理想模型。
    **系统特征树**最多可以显示三个级别的特征，通常称为1级（L1）、2级（L2）和3级（L3）。L2特征是L1特征的子特征，L3特征是L2特征的子特征."""
        )
        if artifact:
            feature_tree = get_feature_tree()
            result += (
        "以下是附录中的**系统特征树**部分：\n"
        f"{feature_tree}\n"
    )

    if "context_diagram" in reference:
        result += (
        "你的可参考**需求工件**包括**上下文图**，\n"
        "**上下文图**用于表述软件系统的范围\n"
        "**上下文图**表述了软件系统与所有外部实体之间的交互关系，"
        )
        if artifact:
            context_diagram = get_context_diagram()
            result += (  
        "以下是附录中的**上下文图**部分：\n"
        f"{context_diagram}\n"
    )

    if "user_introduction" in reference:
        result += (
        "你的可参考**需求工件**包括**用户类与特征**，\n"
        "**用户类与特征**描述了软件系统的可能用户群体，包括用户类名称、用户画像和用户类别描述"
        )
        if artifact:
            user_introduction = get_user_introduction()
            result += (
        "以下是附录中的**用户类与特征**部分：\n"
        f"{user_introduction}\n"
    )

    if "data_flow_diagram" in reference:
        result += (
        "你的可参考**需求工件**包括**数据流图**，\n"
        "该**数据流图**从业务流程的视角出发，系统性刻画了系统中"
        "各类业务数据在外部实体、处理过程与数据存储之间的流转关系，"
        "用于说明系统“处理哪些数据、数据如何流动、在哪些环节被存储或使用”。\n\n"
        "具体而言，**数据流图**包含但不限于以下核心要素：\n"
        "1. **外部实体（External Entities）**：\n"
        "   明确与系统发生数据交互的外部参与方，包括人员或外部知识库"
        "   用于界定数据输入与输出的来源和去向。\n"
        "2. **处理过程（Processes）**：\n"
        "   以逻辑处理单元的形式描述系统对数据执行的关键业务处理活动，"
        "3. **数据存储（Data Stores）**：\n"
        "   标识系统中需要被持久化或集中管理的关键数据集合，"
        "4. **数据流（Data Flows）**：\n"
        "   通过有向连线明确数据在外部实体、处理过程与数据存储之间的传递关系，"
        "   并以简要文字标注数据的业务语义，确保信息流动清晰、可理解。\n"
        )
        if artifact:
            data_flow_diagram = get_data_flow_diagram()
            result += (
        "以下是附录中的**数据流图**部分：\n"
        f"{data_flow_diagram}\n"
    )

    if "data_dictionary" in reference:
        result += (
        "你的可参考**需求工件**包括**数据字典**，\n"
        "**数据字典**是有关应用程序中使用的数据实体的详细信息的集合。将有关组成、数据类型、允许值等的信息收集到共享资源中，可以识别数据验证标准，帮助开发人员正确编写程序，并最大限度地减少集成问题。"
        "**数据字典**常用于表示软件项目的详细数据要求。\n\n"
        )
        if artifact:
            data_dictionary = get_data_dictionary()
            result += (
        "以下是附录中的**数据字典**部分：\n"
        f"{data_dictionary}\n"
    )

    if "dialog_map" in reference:
       
        result += (
        "你的可参考**需求工件**包括**对话图**，\n"
        "**对话图**代表了一个高抽象层次的用户界面设计。"
        "它显示了系统中的对话框元素以及它们之间的导航链接，但它不显示详细的屏幕设计。"
        "**对话图**实际上是一个以状态转换图的形式建模的用户界面。"
        "**对话图**常被用来表现需求中的外部接口部分。"
        )
        if artifact:
            dialog_map = get_dialog_map()
            result += (
        "以下是附录中的**对话图**部分：\n"
        f"{dialog_map}\n"
    )

    if "BRD" in reference:
        result += (
        "你的可参考**需求工件**包括**远景和范围文档**，\n"
        "**远景和范围文档**将业务需求收集到一个单独的可交付成果中，为后续的开发工作奠定基础。"
        "**远景和范围文档**包括了软件的业务需求，待开发软件系统的范围和业务的上下文"
        )
        if artifact:
            BRD = get_BRD().get_whole_document()
            result += (
        "以下是附录中的**远景和范围文档**部分\n"
        f"{BRD}\n"
    )

    if "use_case" in reference:
        result += (
        "你的可参考**需求工件**包括**用例**，\n"
        "**用例**描述了系统和外部行为者之间的一系列互动，导致行为者能够实现一些有价值的结果。\n\n"
        "**用例**常用于表述软件项目的用户需求。\n\n"
        "具体而言，**用例**包含但不限于以下内容：\n"
        "1. **用例名称与描述（Use Case Name & Description**：\n"
        "   为每一个用例提供清晰、可理解的名称，"
        "   并明确该用例试图帮助用户达成的业务目标。\n"
        "2. **参与者定义（Actors）**：\n"
        "   明确用例的主要参与者（Primary Actor）及相关参与者（Secondary Actors），"
        "   确保用例与用户介绍、上下文图中的外部实体保持一致。\n"
        "3. **触发条件（Trigger）**：\n"
        "   描述引发用例执行的业务事件或用户行为，"
        "   用于说明该用例在什么业务情境下被激活。\n"
        "4. **前置条件（Preconditions）**：\n"
        "   明确用例开始前必须满足的系统状态与业务条件，"
        "   例如身份认证通过、数据已准备完毕等。\n"
        "5. **后置条件（Postconditions）**：\n"
        "   描述用例成功完成后系统应达到的状态或产生的结果，"
        "   用于校验用例执行是否达成预期目标。\n"
        "6. **主成功场景（Main Flow）**：\n"
        "   按时间顺序描述在无异常情况下，"
        "   用户与系统之间完成目标的标准交互步骤，"
        "   是后续功能需求实现与测试设计的核心依据。\n"
        "7. **备选流程（Alternative Flows）**：\n"
        "   描述在满足特定条件时可能出现的合法变体流程，"
        "   例如导出数据、选择不同查询范围等。\n"
        "8. **异常流程（Exception Flows）**：\n"
        "   刻画在数据异常、权限异常、系统故障等情况下，"
        "   系统应如何响应以及用户可采取的应对方式，"
        "   确保需求覆盖边界场景。\n"
        "9. **优先级（Priority）与业务规则（Business Rules）**：\n"
        "   明确用例在系统整体中的重要程度，"
        "   并提炼与该用例直接相关的关键业务约束与规则。\n"
        "10. **假设与其他约束（Assumptions & Constraints）**：\n"
        "    说明用例成立所依赖的前提假设，"
        "    以及在设计与实现阶段需要额外关注的限制条件。\n\n"
    )
        if artifact:
            UCL = get_user_case()
            result += (
        "以下是附录中的**用例**部分：\n"
        f"{UCL}\n"
    )

    if "survey" in reference:
        result += (
        "你的可参考**需求工件**包括**现有解决方案调研**，\n"
        """**现有解决方案调研**的内容包括：
    1、市场上主要的类似软件项目列表及其相关信息。
    2、从核心功能、软件特征、软件外部实体，涉及用户群体等方面的对比分析。
    3、针对需求中描述的问题现有软件项目的解决方案与解决程度。
    4、相关的行业规范、标准和法律法规的调研内容。"""
    )
        if artifact:
            survey = get_survey()
            result += (
        "以下是附录中的**现有解决方案调研**部分：\n"
        f"{survey}\n"
    )
    if "ERD" in reference:
        result += (
        "你的可参考**需求工件**包括**实体关系图**，\n"
        "**实体关系图**表述了软件系统中的核心数据实体、"
        "实体属性及其相互关系，"
        "**实体关系图**表示软件项目的数据需求，展示了数据实体之间的逻辑关系。\n\n"
        )
        if artifact:
            ERD = get_ERD()
            result += (
        "以下是附录中的**实体关系图**部分：\n"
        f"{ERD}\n"
    )
    if "non_functional_requirements" in reference:
        result += (
        "你的可参考**需求工件**包括**非功能性需求**，\n"
        "该部分用于明确系统在性能、安全、可用性、可维护性等方面必须达到什么水平"
        )        
        if artifact:
            NFR = get_non_functional_requirements() 
            result += (
        "以下是附录中的**非功能性需求**部分：\n"
        f"{NFR}\n"
    )
    if "usage_scenario" in reference:
        result += (
        "你的可参考**需求工件**包括**使用场景**，\n"
        "**使用场景**从真实业务环境和用户视角出发，"
        "系统性描述在特定业务背景、触发条件和约束下，"
        "不同角色在教学与教务管理过程中所面临的问题、目标以及对系统的期望支持，"

        )        
        if artifact:
            usage_scenario = get_usage_scenario()
            result += (
        "以下是附录中的**使用场景**部分：\n"
        f"{usage_scenario}\n"
    )


    return result
