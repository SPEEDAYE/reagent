# util/util.py — Thread-safe paths, interrupt handling, artifact getters.
#
# Outline:
#   Thread-safe path state (per-project output dir):
#     get_store_path()              returns thread-local or global fallback
#     set_store_path(path)          called at pipeline start (creates dir)
#
#   Interrupt/resume protocol (API mode):
#     _feedback_registry            pid → {event, value}
#     register_feedback_slot(pid)   called by ExecutionService.start
#     unregister_feedback_slot(pid)
#     submit_feedback(pid, value)   called from resume endpoint; sets event
#     set_stream_callback(fn)       injects SSE emitter (_emit)
#     multiline_input(prompt_text, project_id, interrupt_data)
#                                   CLI: prompt_toolkit with empty-line submit
#                                   API: emit interrupt SSE + event.wait()
#
#   Parsing:
#     print_doc_content(d)          formats chapter plan dict to text
#     split_markdown_by_h2(md)      splits by ## headers
#     parse_artifact_dependencies(raw) literal_eval with comment strip
#     read_markdown(path)           UTF-8 read
#
#   Artifact getters (return .md content, raise FileNotFoundError if missing):
#     get_survey, get_feature_tree, get_context_diagram, get_event_list,
#     get_user_introduction, get_business_scope, get_BRD (pickle),
#     get_user_case (pickle), get_usage_scenario, get_state_transition_diagram,
#     get_functional_requirements, get_non_functional_requirements, get_ERD,
#     get_competitive_analysis, get_project_name, get_business_process,
#     get_SRS_chapter, get_SRS_planning, get_document_skeleton,
#     get_artifact_planing (parses via ast.literal_eval)
from pathlib import Path
import os
import json
import pickle
import ast
import re
import threading

# ---------------------------------------------------------------------------
# Per-project output path (thread-safe via threading.local)
# ---------------------------------------------------------------------------
_thread_local = threading.local()
_global_store_path = "output"


def get_store_path() -> str:
    """Return the current store_path.

    CrewAI may hop across helper threads internally, so we keep a process-level
    fallback in addition to thread-local storage.
    """
    return getattr(_thread_local, 'store_path', _global_store_path)


def set_store_path(path: str):
    """Set store_path for the current thread (called at pipeline start)."""
    global _global_store_path
    _thread_local.store_path = path
    _global_store_path = path
    os.makedirs(path, exist_ok=True)


from prompt_toolkit import prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.document import Document

FIELDS = ['chapter_index', 'chapter_title', 'chapter_role', 'chapter_content_focus', 'recommended_expression_form']

def print_doc_content(d):
    return '\n'.join(
        f"{k}: {d[k]}"
        for k in FIELDS
        if k in d
    )

# ---------------------------------------------------------------------------
# API mode: interrupt/resume via threading.Event
# ---------------------------------------------------------------------------
_feedback_registry: dict[str, dict] = {}
_stream_callback = None  # Injected by backend to emit SSE interrupt events


def register_feedback_slot(project_id: str):
    """Register a feedback wait-slot for a project (called before pipeline start)."""
    _feedback_registry[project_id] = {
        "event": threading.Event(),
        "value": None,
    }


def unregister_feedback_slot(project_id: str):
    _feedback_registry.pop(project_id, None)


def submit_feedback(project_id: str, feedback: str):
    """Called from the resume API endpoint to unblock the worker thread."""
    slot = _feedback_registry.get(project_id)
    if slot:
        slot["value"] = feedback
        slot["event"].set()


def set_stream_callback(callback):
    """Inject the SSE event emitter (called once at backend startup)."""
    global _stream_callback
    _stream_callback = callback


def emit_event(project_id: str, event_type: str, **payload):
    """Emit a generic SSE event from anywhere in the worker thread.
    Safe no-op when running in CLI mode (no callback registered)."""
    if project_id and _stream_callback:
        _stream_callback(project_id, event_type, **payload)


def multiline_input(prompt_text="请输入反馈：", project_id=None, interrupt_data=None):
    """
    CLI mode (project_id=None): blocks on terminal input (original behaviour).
    API mode (project_id set): emits an SSE interrupt event, then blocks
    the worker thread on a threading.Event until submit_feedback() is called.
    """
    if project_id and project_id in _feedback_registry:
        # --- API mode ---
        # Notify the frontend that we need input
        if interrupt_data and _stream_callback:
            _stream_callback(project_id, "interrupt", **interrupt_data)

        slot = _feedback_registry[project_id]
        slot["event"].clear()
        slot["event"].wait()  # blocks worker thread only, not the async loop
        value = slot["value"]
        slot["value"] = None
        return value if value else "no"

    # --- CLI mode (original logic) ---
    kb = KeyBindings()
    session = PromptSession(key_bindings=kb, multiline=True)

    @kb.add("enter")
    def _(event):
        buffer = event.app.current_buffer
        text = buffer.text

        # 判断是否已经是"空行结尾"
        if text.endswith("\n\n"):
            buffer.validate_and_handle()
        else:
            buffer.insert_text("\n")

    try:
        text = session.prompt(prompt_text)
    except (EOFError, KeyboardInterrupt):
        return "exit"

    text = text.strip()
    if not text:
        return "no"
    if text.lower() == "exit":
        return "exit"
    return text

def split_markdown_by_h2(md_text: str) -> list[str]:
    pattern = re.compile(r'(?m)(?=^##\s+)')
    sections = [s.strip() for s in pattern.split(md_text) if s.strip()]
    return sections


def parse_artifact_dependencies(raw_text: str):
    """
    将 AI 输出的 Python 列表（含注释）解析为 list[list[str]]
    """
    # 1. 去掉所有行尾注释
    cleaned = re.sub(r"#.*", "", raw_text)

    # 2. 去掉空行
    cleaned = "\n".join(line for line in cleaned.split("\n") if line.strip())

    # 3. 转换为真正的 Python 对象
    try:
        result = ast.literal_eval(cleaned)
    except Exception as e:
        raise ValueError(f"解析 artifact planning 失败: {e}\n清理后的内容:\n{cleaned}")

    return result


def read_markdown(file_path: str) -> str:
    """
    读取 markdown 文件内容并返回为字符串
    :param file_path: .md 文件路径
    :return: 文件内容字符串
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")
    
    # 根据需要调整 encoding，例如 'utf-8-sig'
    with path.open('r', encoding='utf-8') as f:
        content = f.read()
    return content

def get_user_case(file_path: str = None) -> dict:
    """
    读取用户用例的 JSON 文件内容并返回为字典
    :param file_path: 用户用例 JSON 文件路径
    :return: 文件内容字典
    """
    if file_path is None:
        file_path = f"{get_store_path()}/UseCase.pkl"
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"User case file not found: {file_path}")
    
    with path.open('rb') as f:
        UCL = pickle.load(f)
    result = ''
    for uc in UCL:
        result += uc.get_usecase() + "\n"

    return result

def get_project_name():
    if os.path.exists(f'{get_store_path()}/project_name.md'):
        return read_markdown(f'{get_store_path()}/project_name.md')
    else:
        raise FileNotFoundError("project name file not found.")

def get_business_process():
    if os.path.exists(f'{get_store_path()}/business_process_diagram.md'):
        return read_markdown(f'{get_store_path()}/business_process_diagram.md')
    else:
        raise FileNotFoundError("business_process_diagram file not found.")
    
def get_state_transition_diagram():
    if os.path.exists(f'{get_store_path()}/state_transition_diagram.md'):
        return read_markdown(f'{get_store_path()}/state_transition_diagram.md')
    else:
        raise FileNotFoundError("state_transition_diagram file not found.")

def get_feature_tree():
    if os.path.exists(f'{get_store_path()}/feature_tree.md'):
        return read_markdown(f'{get_store_path()}/feature_tree.md')
    else:
        raise FileNotFoundError("feature tree file not found.")
    
def get_context_diagram():
    if os.path.exists(f'{get_store_path()}/draft_context_diagram.md'):
        return read_markdown(f'{get_store_path()}/draft_context_diagram.md')
    else:
        raise FileNotFoundError("Context diagram file not found.")
    
def get_functional_requirements():
    if os.path.exists(f'{get_store_path()}/functional_requirements.md'):
        return read_markdown(f'{get_store_path()}/functional_requirements.md')
    else:
        raise FileNotFoundError("Functional requirements file not found.")
    
def get_event_list():
    if os.path.exists(f'{get_store_path()}/draft_event_list.md'):
        return read_markdown(f'{get_store_path()}/draft_event_list.md')
    else:
        raise FileNotFoundError("Event list file not found.")

def get_business_scope():
    if os.path.exists(f'{get_store_path()}/business_scope.md'):
        return read_markdown(f'{get_store_path()}/business_scope.md')
    else:
        raise FileNotFoundError("business_scope file not found.")

def get_ERD():
    if os.path.exists(f'{get_store_path()}/entity_relationship_diagram.md'):
        return read_markdown(f'{get_store_path()}/entity_relationship_diagram.md')
    else:
        raise FileNotFoundError("ERD file not found.")

def get_usage_scenario():
    if os.path.exists(f'{get_store_path()}/usage_scenario.md'):
        return read_markdown(f'{get_store_path()}/usage_scenario.md')
    else:
        raise FileNotFoundError("Usage scenario file not found.")
    
def get_user_introduction():
    if os.path.exists(f'{get_store_path()}/user_introduction.md'):
        return read_markdown(f'{get_store_path()}/user_introduction.md')
    else:
        raise FileNotFoundError("User introduction file not found.")

def get_competitive_analysis():
    if os.path.exists(f'{get_store_path()}/competitive_analysis.md'):
        return read_markdown(f'{get_store_path()}/competitive_analysis.md')
    else:
        raise FileNotFoundError("Competitive analysis file not found.")
    
def get_survey():
    if os.path.exists(f'{get_store_path()}/survey.md'):
        return read_markdown(f'{get_store_path()}/survey.md')
    else:
        raise FileNotFoundError("Survey file not found.")

def get_BRD():
    if os.path.exists(f'{get_store_path()}/BusinessRequirementDocument.pkl'):
        import pickle
        with open(f"{get_store_path()}/BusinessRequirementDocument.pkl",'rb') as f:
            BRD = pickle.load(f)
        return BRD
    else:
        raise FileNotFoundError("Business Requirement Document file not found.")
    
def get_data_flow_diagram():
    if os.path.exists(f'{get_store_path()}/data_flow_diagram.md'):
        return read_markdown(f'{get_store_path()}/data_flow_diagram.md')
    else:
        raise FileNotFoundError("Data flow diagram file not found.")
    
def get_data_dictionary():
    if os.path.exists(f'{get_store_path()}/data_dictionary.md'):
        return read_markdown(f'{get_store_path()}/data_dictionary.md')
    else:
        raise FileNotFoundError("Data dictionary file not found.")
    
def get_dialog_map():
    if os.path.exists(f'{get_store_path()}/dialog_map.md'):
        return read_markdown(f'{get_store_path()}/dialog_map.md')
    else:
        raise FileNotFoundError("Dialog map file not found.")
    
def get_SRS_chapter():
    if os.path.exists(f'{get_store_path()}/software_requirements_specification_chapter.md'):
        return read_markdown(f'{get_store_path()}/software_requirements_specification_chapter.md')
    else:
        raise FileNotFoundError("Software Requirement Specification file not found.")
    
def get_SRS_planning():
    if os.path.exists(f'{get_store_path()}/srs_planning.md'):
        return read_markdown(f'{get_store_path()}/srs_planning.md')
    else:
        raise FileNotFoundError("Software Requirement Specification prompt file not found.")
    
def get_document_skeleton():
    if os.path.exists(f'{get_store_path()}/document_skeleton.md'):
        return read_markdown(f'{get_store_path()}/document_skeleton.md')
    else:
        raise FileNotFoundError("Document skeleton file not found.")
    
def get_artifact_planing():
    if os.path.exists(f'{get_store_path()}/artifact_planning.md'):
        return parse_artifact_dependencies(read_markdown(f'{get_store_path()}/artifact_planning.md'))
    else:
        raise FileNotFoundError("Artifact planing file not found.")
    
def get_non_functional_requirements():
    if os.path.exists(f'{get_store_path()}/non_functional_requirements.md'):
        return read_markdown(f'{get_store_path()}/non_functional_requirements.md')
    else:
        raise FileNotFoundError("Non-Functional Requirements file not found.")
    
