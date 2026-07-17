"""Core execution service: wraps the CLI pipeline in a background thread,
emitting SSE events through StreamManager and handling interrupt/resume
via threading.Event in the patched multiline_input().

Outline:
  _executor                 single-worker ThreadPoolExecutor (state isolation)
  _active                   project_id → running future

  _emit(pid, type, **kw)    publish SSE event (also updates project status
                            to 'interrupted' on interrupt events)
  _update_project_status_sync(pid, **fields)
                            fire-and-forget status update via
                            asyncio.run_coroutine_threadsafe

  ExecutionService
    start(pid, config)      register feedback slot + create queue +
                            submit _run_pipeline to executor
    resume(pid, resume_type, human_comment)
                            map resume_type → feedback value; call
                            submit_feedback() to unblock worker

  _run_pipeline(pid, config) runs in worker thread:
    - set cwd, load .env, set_store_path('experiment/{pid}')
    - set CREWAI_STORAGE_DIR for per-project CrewAI storage
    - monkey-patch util.run_with_retry to emit crew_start /
      artifact_complete / error around each crew kickoff
    - sequentially execute 6 stages (MetaAnalysis, BR, Elicitation,
      Analysis, NonStandard, SRS Generation), emitting stage_start /
      stage_complete around each
    - finally: restore run_with_retry, pop from _active
"""

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from backend.services.stream_manager import stream_manager
from backend.services.project_service import ProjectService

# Keep a single active worker to avoid cross-project output-path bleed while the
# underlying CrewAI pipeline still relies on process-global path state.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reagent")
_active: dict[str, threading.Thread | asyncio.Future] = {}

project_svc = ProjectService()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(project_id: str, event_type: str, wait: bool = False, **kwargs) -> bool:
    """Emit an SSE event from a worker thread AND mirror to per-project log."""
    if event_type == "interrupt":
        _update_project_status_sync(
            project_id,
            status="interrupted",
            current_crew=None,
        )
    future = stream_manager.publish_sync(project_id, {
        "type": event_type,
        "project_id": project_id,
        **kwargs,
    })
    delivered = True
    if wait and future is not None:
        try:
            future.result(timeout=10)
        except Exception as exc:
            delivered = False
            try:
                from backend.services.logging_service import get_project_logger
                logger = get_project_logger(project_id)
                logger.warning(
                    "Timed out waiting for terminal SSE %s delivery: %s",
                    event_type,
                    exc,
                )
            except Exception:
                pass
    # Mirror to the per-project pipeline log for post-mortem debugging.
    try:
        from backend.services.logging_service import get_project_logger
        logger = get_project_logger(project_id)
        logger.info("SSE %s: %s", event_type, kwargs)
    except Exception:
        # Never let logging break the pipeline.
        pass
    return delivered


def _update_project_status_sync(project_id: str, **fields):
    """Update project status from a worker thread via the main event loop."""
    loop = stream_manager._loop
    if loop is None:
        return
    asyncio.run_coroutine_threadsafe(
        project_svc.update_status(project_id, **fields), loop
    )


class ExecutionService:

    async def start(self, project_id: str, config: dict):
        if project_id in _active:
            raise RuntimeError(f"Project {project_id} is already running")

        # Register feedback slot for this project
        from util.util import register_feedback_slot, set_stream_callback
        register_feedback_slot(project_id)
        set_stream_callback(_emit)

        # Create SSE queue
        stream_manager.create_queue(project_id)

        # Ensure the stream manager knows the main loop
        loop = asyncio.get_event_loop()
        stream_manager.set_loop(loop)

        # Update project status
        await project_svc.update_status(
            project_id, status="running", current_stage="meta_analysis"
        )

        future = loop.run_in_executor(
            _executor, _run_pipeline, project_id, config
        )
        _active[project_id] = future

    async def resume(self, project_id: str, resume_type: str,
                     human_comment: str | None = None, **kwargs):
        from util.util import submit_feedback

        # UX semantics:
        #   "accept"        -> no feedback, proceed to next step (-> "no")
        #   "feedback"      -> the human_comment is the feedback text; pipeline
        #                       runs modify_agent, re-runs only the affected
        #                       artifacts, then loops back to interrupt.
        #   "redo_artifact" -> force-redo a specific artifact (advanced use).
        # Unknown resume_type fallbacks to "no" for safety.
        feedback_map = {
            "accept": "no",
            "feedback": human_comment or "no",
            "redo_artifact": human_comment or "redo",
        }
        value = feedback_map.get(resume_type, "no")
        await project_svc.update_status(project_id, status="running")
        submit_feedback(project_id, value)
        return {"status": "resumed", "project_id": project_id}


# ---------------------------------------------------------------------------
# Pipeline runner (runs in a worker thread, NOT on the async event loop)
# ---------------------------------------------------------------------------

def _write_run_metadata(project_root, project_id: str, config: dict, project_output: str) -> None:
    """Create academic run metadata files for an API-triggered experiment."""
    from pathlib import Path

    run_dir = project_root / project_output
    run_dir.mkdir(parents=True, exist_ok=True)
    command = f"POST /graph/stream/create project_id={project_id}"
    (run_dir / "command.txt").write_text(command + "\n", encoding="utf-8")
    (run_dir / "README.md").write_text(
        "\n".join([
            f"# {project_id}",
            "",
            "- Script id: api-stream",
            f"- Project: {config.get('project_name', '')}",
            f"- Model id: {os.getenv('REAGENT_MODEL_ID', 'api-model')}",
            f"- Output path: `{project_output}`",
            "",
            "## Command",
            "",
            "```text",
            command,
            "```",
            "",
        ]),
        encoding="utf-8",
    )


def _run_pipeline(project_id: str, config: dict):
    """Execute the full RE pipeline synchronously in a worker thread."""
    import sys
    import os
    import warnings
    from pathlib import Path

    # Setup the same environment as main.py
    warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
    project_root = Path(__file__).resolve().parents[3]
    src_root = project_root / "src"
    reagent_src_dir = src_root / "reagent"
    sys.path.insert(0, str(reagent_src_dir))
    sys.path.insert(0, str(src_root))
    sys.path.insert(0, str(project_root))
    os.chdir(str(project_root))

    from dotenv import load_dotenv
    load_dotenv(str(project_root / ".env"))

    # --- Set per-project output directory (thread-safe) ---
    # Use relative path (relative to cwd which is project_root) because
    # CrewAI's output_file concatenates cwd + output_file path
    from util.util import set_store_path
    project_output = os.path.join("experiment", project_id)
    set_store_path(project_output)
    os.environ["REAGENT_RUN_ID"] = project_id
    os.environ["REAGENT_MODEL_ID"] = (
        os.getenv("LLM_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("DEEPSEEK_MODEL")
        or "api-model"
    )
    os.environ["REAGENT_OUTPUT_PATH"] = project_output
    _write_run_metadata(project_root, project_id, config, project_output)

    # Per-project CrewAI storage
    crewai_storage = os.path.join(str(project_root), project_output, "crewai_storage")
    os.makedirs(crewai_storage, exist_ok=True)
    os.environ["CREWAI_STORAGE_DIR"] = crewai_storage

    # Register run_with_retry event hooks via thread-local
    from util import run_with_retry  # noqa: F401
    import util as util_mod

    _original_run_with_retry = util_mod.run_with_retry

    def _patched_run_with_retry(crew_callable, inputs, name, retries=5,
                                delay=15, post_process_callable=None,
                                post_process_params=None):
        _update_project_status_sync(
            project_id,
            status="running",
            current_stage=config.get("_current_stage", ""),
            current_crew=name,
        )
        _emit(project_id, "crew_start", crew_name=name,
              stage=config.get("_current_stage", ""))
        try:
            result = _original_run_with_retry(
                crew_callable, inputs, name, retries, delay,
                post_process_callable, post_process_params,
            )
            _update_project_status_sync(project_id, current_crew=None)
            _emit(project_id, "artifact_complete", crew_name=name)
            return result
        except Exception as e:
            _update_project_status_sync(project_id, current_crew=None)
            _emit(project_id, "error", crew_name=name, error=str(e),
                  recoverable=True)
            raise

    util_mod.run_with_retry = _patched_run_with_retry

    project_name = config["project_name"]
    description = config["description"]
    srs_example_path = config.get("srs_example_path") or "src/util/doc_template/document_example.md"
    srs_template = config.get("srs_template")

    try:
        # ---- Phase 1: MetaAnalysis ----
        config["_current_stage"] = "meta_analysis"
        _update_project_status_sync(
            project_id,
            status="running",
            current_stage="meta_analysis",
            current_crew=None,
        )
        _emit(project_id, "stage_start", stage="meta_analysis",
              stage_index=1, total_stages=6, stage_label="元分析阶段")

        from StandardProcess import MetaAnalysisrun
        result = MetaAnalysisrun(
            doc_example_path=srs_example_path,
            SRS_template=srs_template,
            project_name=project_name,
            Description=description,
        )
        doc_template, doc_skeleton, doc_planning, ch_dep, art_plan = result
        _emit(project_id, "stage_complete", stage="meta_analysis")

        # ---- Phase 2: Business Requirements (2 interrupts) ----
        config["_current_stage"] = "business_requirements"
        _update_project_status_sync(
            project_id,
            status="running",
            current_stage="business_requirements",
            current_crew=None,
        )
        _emit(project_id, "stage_start", stage="business_requirements",
              stage_index=2, total_stages=6, stage_label="业务需求阶段")

        from StandardProcess import BRDevrun
        BRDevrun(
            project_name=project_name,
            Description=description,
            project_id=project_id,
        )
        _emit(project_id, "stage_complete", stage="business_requirements")

        # ---- Phase 3: Requirement Elicitation (1 interrupt) ----
        config["_current_stage"] = "requirement_elicitation"
        _update_project_status_sync(
            project_id,
            status="running",
            current_stage="requirement_elicitation",
            current_crew=None,
        )
        _emit(project_id, "stage_start", stage="requirement_elicitation",
              stage_index=3, total_stages=6, stage_label="需求获取阶段")

        from StandardProcess import RequirementElicitationrun
        RequirementElicitationrun(
            project_name=project_name,
            Description=description,
            project_id=project_id,
        )
        _emit(project_id, "stage_complete", stage="requirement_elicitation")

        # ---- Phase 4: Requirement Analysis ----
        config["_current_stage"] = "requirement_analysis"
        _update_project_status_sync(
            project_id,
            status="running",
            current_stage="requirement_analysis",
            current_crew=None,
        )
        _emit(project_id, "stage_start", stage="requirement_analysis",
              stage_index=4, total_stages=6, stage_label="需求分析阶段")

        from StandardProcess import RequirementAnalysisrun
        RequirementAnalysisrun(
            project_name=project_name,
            Description=description,
            artifact_planing=art_plan,
        )
        _emit(project_id, "stage_complete", stage="requirement_analysis")

        # ---- Phase 5: Non-Standard ----
        config["_current_stage"] = "non_standard"
        _update_project_status_sync(
            project_id,
            status="running",
            current_stage="non_standard",
            current_crew=None,
        )
        _emit(project_id, "stage_start", stage="non_standard",
              stage_index=5, total_stages=6, stage_label="非标准制品阶段")

        from NonStandardProcess import NonStandardProcessrun
        NonStandardProcessrun(
            project_name=project_name,
            Description=description,
            artifact_planing=art_plan,
        )
        _emit(project_id, "stage_complete", stage="non_standard")

        # ---- Phase 6: SRS Generation ----
        config["_current_stage"] = "srs_generation"
        _update_project_status_sync(
            project_id,
            status="running",
            current_stage="srs_generation",
            current_crew=None,
        )
        _emit(project_id, "stage_start", stage="srs_generation",
              stage_index=6, total_stages=6, stage_label="SRS 生成阶段")

        # Import from the reagent main module
        from main import RequirementSpecificationrun
        RequirementSpecificationrun(
            document_template=doc_template,
            document_skeleton=doc_skeleton,
            doc_content=doc_planning,
            chapter_dependence=ch_dep,
            SRS_Reference=art_plan,
            srs_example_path=srs_example_path,
        )
        _emit(project_id, "stage_complete", stage="srs_generation")

        # ---- Done ----
        _update_project_status_sync(
            project_id,
            status="completed",
            current_stage=None,
            current_crew=None,
        )
        completion_payload = {
            "status": "completed",
            "total_artifacts": 17,
            "srs_generated": True,
        }
        _emit(
            project_id,
            "completed",
            wait=True,
            **completion_payload,
        )
        _emit(
            project_id,
            "finished",
            wait=True,
            **completion_payload,
        )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        # Capture a full error context dump BEFORE updating status so the log
        # retains the live stack trace with the project's in-flight state.
        try:
            from backend.services.logging_service import log_error_context
            log_error_context(
                project_id, e,
                stage=config.get("_current_stage"),
                project_name=config.get("project_name"),
                srs_template=config.get("srs_template"),
                srs_example_path=config.get("srs_example_path"),
            )
        except Exception:
            pass

        _update_project_status_sync(
            project_id,
            status="error",
            current_stage=config.get("_current_stage"),
            current_crew=None,
            last_error=error_msg,
        )
        _emit(project_id, "error", wait=True, error=error_msg, recoverable=False)
    finally:
        _active.pop(project_id, None)
        # Restore original run_with_retry
        util_mod.run_with_retry = _original_run_with_retry
        # Release the live SSE queue but keep event history in memory for
        # the TTL window so reconnecting clients can replay.
        try:
            stream_manager.remove_queue(project_id)
        except Exception:
            pass
