"""Process-isolated pipeline execution with IPC-backed events and feedback.

Outline:
  ProcessPoolExecutor       configurable multi-project process isolation
  Manager queues            per-project events, feedback and cancellation
  _active / _ipc            API-process runtime registry keyed by project_id
  StreamManager             live SSE delivery plus persisted event replay

  _run_pipeline(pid, config) runs in a spawned worker process:
    - set cwd, load .env, set_store_path('experiment/{pid}')
    - set CREWAI_STORAGE_DIR for per-project CrewAI storage
    - monkey-patch util.run_with_retry to emit crew_start /
      artifact_complete / error around each crew kickoff
    - sequentially execute 6 stages (MetaAnalysis, BR, Elicitation,
      Analysis, NonStandard, SRS Generation), emitting stage_start /
      stage_complete around each
    - finally: restore run_with_retry and signal the API event pump
"""

import asyncio
import hashlib
import json
import os
import queue as std_queue
import threading
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timezone

from backend.services.stream_manager import stream_manager
from backend.services.project_service import ProjectService
from backend.services.run_service import RunService
from backend.services.artifact_service import ARTIFACT_META
from backend.config import settings

_executor: ProcessPoolExecutor | None = None
_manager = None
_runtime_lock = threading.Lock()
_active: dict[str, asyncio.Future] = {}
_ipc: dict[str, dict] = {}
# Compatibility bridge while SSE subscriptions are still keyed by project_id.
_project_runs: dict[str, str] = {}

# These are populated only inside a spawned worker process.
_worker_event_queue = None
_worker_cancel_event = None

# Track projects that have been cancelled (e.g. via DELETE) so that
# _patched_run_with_retry can check before each crew kickoff.
_cancelled_projects: set[str] = set()
_cancel_lock = threading.Lock()

project_svc = ProjectService()
run_svc = RunService()


def _srs_completion_marker(project_id: str, run_id: str | None) -> dict | None:
    """Return a verified SRS commit marker, never infer completion from existence."""
    output_dir = (
        os.path.join(settings.OUTPUT_DIR, project_id, "runs", run_id)
        if run_id
        else os.path.join(settings.OUTPUT_DIR, project_id)
    )
    marker_path = os.path.join(output_dir, ".pipeline", "srs_complete.json")
    try:
        with open(marker_path, "r", encoding="utf-8") as marker_file:
            marker = json.load(marker_file)
        if marker.get("completed") is not True or marker.get("chapter_count", 0) < 1:
            return None
        expected_files = marker.get("files") or {}
        for filename in ("SRS.md", "SRS.pkl"):
            expected_hash = expected_files.get(filename)
            if not expected_hash:
                return None
            digest = hashlib.sha256()
            with open(os.path.join(output_dir, filename), "rb") as artifact_file:
                for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected_hash:
                return None
        return marker
    except (OSError, ValueError, TypeError):
        return None


async def _reconcile_completed_srs(project_id: str, run_id: str | None) -> bool:
    if not _srs_completion_marker(project_id, run_id):
        return False
    await _update_project_and_run(
        project_id,
        run_id,
        status="completed",
        current_stage=None,
        current_crew=None,
        last_error=None,
    )
    shared = {
        "project_id": project_id,
        "run_id": run_id,
        "reconciled_after_worker_exit": True,
    }
    await stream_manager.publish(project_id, {
        "type": "artifact_complete",
        "crew_name": "SRS",
        "stage": "srs_generation",
        **_artifact_event_fields("SRS"),
        **shared,
    })
    await stream_manager.publish(project_id, {
        "type": "stage_complete",
        "stage": "srs_generation",
        **shared,
    })
    completion = {
        "status": "completed",
        "total_artifacts": 17,
        "srs_generated": True,
        **shared,
    }
    await stream_manager.publish(project_id, {"type": "completed", **completion})
    await stream_manager.publish(project_id, {"type": "finished", **completion})
    return True

# CrewAI 执行名 -> 后端标准制品键。未列出的 Crew 都是内部步骤，
# 只能发送 crew_start/crew_complete，不能伪装成 artifact_complete。
CREW_ARTIFACT_NAMES: dict[str, str] = {
    "SurveyCrew": "survey",
    "DraftContentDiagramCrew": "context_diagram",
    "DraftEventListCrew": "event_list",
    "UserIntroductionDev": "user_introduction",
    "FeatureTreeDev": "feature_tree",
    "BusinessScopeDev": "business_scope",
    "UserCaseCrew": "use_case",
    "NFRCrew": "non_functional_requirements",
    "FRCrew": "functional_requirements",
    "DataFlowDiagramCrew": "data_flow_diagram",
    "ERDCrew": "ERD",
    "DataDictionaryCrew": "data_dictionary",
    "DialogMapCrew": "dialog_map",
    "UsageScenarioCrew": "usage_scenario",
    "STDCrew": "state_transition_diagram",
}


def _artifact_event_fields(artifact_name: str) -> dict:
    display_name = ARTIFACT_META.get(artifact_name, (artifact_name, ""))[0]
    return {
        "artifact_name": artifact_name,
        "display_name": display_name,
        "produces_artifact": True,
    }


def _crew_event_fields(crew_name: str) -> dict:
    artifact_name = CREW_ARTIFACT_NAMES.get(crew_name)
    if not artifact_name:
        return {"produces_artifact": False}
    return _artifact_event_fields(artifact_name)


def _get_process_runtime():
    global _executor, _manager
    with _runtime_lock:
        if _manager is None:
            context = multiprocessing.get_context("spawn")
            _manager = context.Manager()
        if _executor is None:
            context = multiprocessing.get_context("spawn")
            _executor = ProcessPoolExecutor(
                max_workers=settings.PIPELINE_MAX_WORKERS,
                mp_context=context,
            )
        return _executor, _manager


def _discard_broken_executor(expected_executor=None) -> bool:
    """Drop a poisoned process pool so the next submission gets a fresh one.

    ``ProcessPoolExecutor`` cannot be reused after any worker exits abruptly.
    Several event pumps can observe the same failure concurrently, therefore
    only the pump that still owns the current executor is allowed to clear it.
    """
    global _executor
    with _runtime_lock:
        if _executor is None:
            return False
        if expected_executor is not None and _executor is not expected_executor:
            return False
        broken_executor = _executor
        _executor = None
    try:
        broken_executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    return True


def _ipc_probe_worker(event_queue, feedback_queue):
    """Small picklable probe used by deployment smoke tests."""
    worker_pid = os.getpid()
    event_queue.put({"worker_pid": worker_pid})
    feedback = feedback_queue.get(timeout=10)
    return {"worker_pid": worker_pid, "feedback": feedback}


def _ipc_test_pipeline(project_id, config, event_queue, feedback_queue, cancel_event):
    """Deterministic lightweight worker used by concurrency integration tests."""
    import time

    run_id = config.get("_run_id")
    worker_pid = os.getpid()
    event_queue.put({
        "type": "__status__",
        "fields": {"status": "running", "current_stage": "probe"},
    })
    event_queue.put({
        "type": "stage_start",
        "project_id": project_id,
        "run_id": run_id,
        "stage": "probe",
        "worker_pid": worker_pid,
    })
    feedback = feedback_queue.get(timeout=10)
    if cancel_event.is_set() or feedback == "__CANCEL__":
        event_queue.put({
            "type": "cancelled",
            "project_id": project_id,
            "run_id": run_id,
            "worker_pid": worker_pid,
        })
    else:
        time.sleep(0.1)
        event_queue.put({
            "type": "feedback_received",
            "project_id": project_id,
            "run_id": run_id,
            "feedback": feedback,
            "worker_pid": worker_pid,
        })
        event_queue.put({
            "type": "completed",
            "project_id": project_id,
            "run_id": run_id,
            "worker_pid": worker_pid,
        })
        event_queue.put({
            "type": "__status__",
            "fields": {"status": "completed", "current_stage": None},
        })
    event_queue.put({"type": "__worker_done__"})


async def shutdown_execution_runtime() -> None:
    """Best-effort shutdown for worker processes and their IPC manager."""
    global _executor, _manager
    for ipc in list(_ipc.values()):
        try:
            ipc["cancel_event"].set()
            ipc["feedback_queue"].put("__CANCEL__")
        except Exception:
            pass
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
    if _manager is not None:
        try:
            _manager.shutdown()
        except Exception:
            pass
        _manager = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(project_id: str, event_type: str, wait: bool = False, **kwargs) -> bool:
    """Emit through process IPC (worker) or directly to SSE (API process)."""
    if event_type == "interrupt":
        _update_project_status_sync(
            project_id,
            status="interrupted",
            current_crew=None,
        )
    elif event_type == "interrupt_auto_skipped":
        _update_project_status_sync(
            project_id,
            status="running",
            current_crew=None,
        )
    run_id = _project_runs.get(project_id)
    event = {
        "type": event_type,
        "project_id": project_id,
        **({"run_id": run_id} if run_id else {}),
        **kwargs,
    }
    if _worker_event_queue is not None:
        event.setdefault("timestamp", _now())
        _worker_event_queue.put(event)
        future = None
    else:
        future = stream_manager.publish_sync(project_id, event)
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


async def _update_project_and_run(project_id: str, run_id: str | None, **fields):
    await project_svc.update_status(project_id, **fields)
    if run_id:
        await run_svc.update_status(run_id, **fields)


def _update_project_status_sync(project_id: str, **fields):
    """Mirror status through IPC or the API event loop."""
    loop = stream_manager._loop
    if loop is None:
        if _worker_event_queue is not None:
            _worker_event_queue.put({
                "type": "__status__",
                "project_id": project_id,
                "run_id": _project_runs.get(project_id),
                "fields": fields,
            })
        return
    asyncio.run_coroutine_threadsafe(
        _update_project_and_run(
            project_id, _project_runs.get(project_id), **fields
        ), loop
    )


class ExecutionService:

    def __init__(self, worker_target=None):
        self._worker_target = worker_target or _run_pipeline

    async def start(self, project_id: str, config: dict, run_id: str | None = None):
        if project_id in _active:
            raise RuntimeError(f"Project {project_id} is already running")

        executor, manager = _get_process_runtime()
        event_queue = manager.Queue()
        feedback_queue = manager.Queue()
        cancel_event = manager.Event()

        # Create SSE queue
        stream_manager.create_queue(project_id, run_id=run_id)
        if run_id:
            _project_runs[project_id] = run_id
            config["_run_id"] = run_id

        # Ensure the stream manager knows the main loop
        loop = asyncio.get_event_loop()
        stream_manager.set_loop(loop)

        # The process pool may queue this run until a worker becomes free.
        await project_svc.update_status(
            project_id,
            status="queued",
            current_stage=None,
            current_run_id=run_id,
        )
        if run_id:
            await run_svc.update_status(run_id, status="queued", current_stage=None)
        await stream_manager.publish(project_id, {
            "type": "queued",
            "project_id": project_id,
            "run_id": run_id,
            "message": "Pipeline entered the process-worker queue",
        })

        try:
            future = loop.run_in_executor(
                executor,
                self._worker_target,
                project_id,
                config,
                event_queue,
                feedback_queue,
                cancel_event,
            )
        except BrokenProcessPool:
            # A previous worker crash poisons the whole executor. This task was
            # rejected before submission, so rebuilding and retrying it once is
            # safe and does not duplicate pipeline work.
            _discard_broken_executor(executor)
            executor, _ = _get_process_runtime()
            try:
                future = loop.run_in_executor(
                    executor,
                    self._worker_target,
                    project_id,
                    config,
                    event_queue,
                    feedback_queue,
                    cancel_event,
                )
            except BrokenProcessPool as exc:
                _discard_broken_executor(executor)
                raise RuntimeError(
                    "Pipeline process pool could not be restarted; "
                    "please retry after checking worker memory and logs"
                ) from exc
        _active[project_id] = future
        _ipc[project_id] = {
            "run_id": run_id,
            "event_queue": event_queue,
            "feedback_queue": feedback_queue,
            "cancel_event": cancel_event,
        }
        _ipc[project_id]["pump_task"] = loop.create_task(
            self._pump_worker_events(
                project_id, run_id, event_queue, future, executor
            )
        )

    async def _pump_worker_events(
        self,
        project_id: str,
        run_id: str | None,
        event_queue,
        future,
        executor,
    ) -> None:
        """Bridge process-safe worker events into SSE and persistent storage."""
        terminal_seen = False
        try:
            while True:
                try:
                    event = await asyncio.to_thread(event_queue.get, True, 1)
                except std_queue.Empty:
                    if future.done():
                        break
                    continue
                event_type = event.get("type")
                if event_type == "__worker_done__":
                    break
                if event_type == "__status__":
                    await _update_project_and_run(
                        project_id, run_id, **event.get("fields", {})
                    )
                    continue
                terminal_seen = terminal_seen or event_type in {
                    "completed", "finished", "cancelled"
                } or (event_type == "error" and not event.get("recoverable", False))
                await stream_manager.publish(project_id, event)

            try:
                await future
            except Exception as exc:
                if isinstance(exc, BrokenProcessPool):
                    _discard_broken_executor(executor)
                if not terminal_seen:
                    if (
                        isinstance(exc, BrokenProcessPool)
                        and await _reconcile_completed_srs(project_id, run_id)
                    ):
                        terminal_seen = True
                        return
                    if isinstance(exc, BrokenProcessPool):
                        error = (
                            "Worker process exited unexpectedly; the process pool "
                            "was reset automatically. Check worker memory/native "
                            "dependency logs, then start the pipeline again."
                        )
                    else:
                        error = f"Worker process failed: {type(exc).__name__}: {exc}"
                    await _update_project_and_run(
                        project_id,
                        run_id,
                        status="error",
                        current_crew=None,
                        last_error=error,
                    )
                    await stream_manager.publish(project_id, {
                        "type": "error",
                        "project_id": project_id,
                        "run_id": run_id,
                        "error": error,
                        "recoverable": False,
                    })
        finally:
            _active.pop(project_id, None)
            _ipc.pop(project_id, None)
            _project_runs.pop(project_id, None)
            stream_manager.remove_queue(project_id)

    async def resume(
        self,
        project_id: str,
        resume_type: str,
        human_comment: str | None = None,
        target_artifact: str | None = None,
        target_artifacts: list[str] | None = None,
        **kwargs,
    ):
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
        targets = list(dict.fromkeys(
            name for name in (target_artifacts or [target_artifact]) if name
        ))
        if targets and value != "no":
            value = (
                f"目标制品：{', '.join(targets)}\n"
                f"反馈意见：{value}"
            )
        ipc = _ipc.get(project_id)
        if not ipc:
            raise RuntimeError("Pipeline worker is not active; it may have restarted")
        await project_svc.update_status(project_id, status="running")
        ipc["feedback_queue"].put(value)
        run_id = _project_runs.get(project_id)
        if run_id:
            await run_svc.update_status(run_id, status="running")
        return {
            "status": "resumed",
            "project_id": project_id,
            "run_id": run_id,
            "target_artifacts": targets,
        }

    async def mark_interrupt_active(self, project_id: str) -> dict:
        ipc = _ipc.get(project_id)
        if not ipc:
            raise RuntimeError("Pipeline worker is not active; it may have restarted")
        ipc["feedback_queue"].put("__HUMAN_ACTIVE__")
        return {
            "status": "activity_acknowledged",
            "project_id": project_id,
            "run_id": _project_runs.get(project_id),
        }

    async def cancel(self, project_id: str) -> dict:
        """Signal cancellation across the worker-process boundary."""
        result = {"project_id": project_id, "action": "none"}
        ipc = _ipc.get(project_id)
        run_id = _project_runs.get(project_id)
        if not ipc:
            result["action"] = "cleaned_up"
            return result
        ipc["cancel_event"].set()
        ipc["feedback_queue"].put("__CANCEL__")
        result["action"] = "cancel_signalled"
        await project_svc.update_status(
            project_id, status="cancelled", current_stage=None, current_crew=None
        )
        if run_id:
            await run_svc.update_status(
                run_id, status="cancelled", current_stage=None, current_crew=None
            )
        return result


# ---------------------------------------------------------------------------
# Pipeline runner (runs in a spawned worker process)
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


def _run_pipeline(
    project_id: str,
    config: dict,
    event_queue=None,
    feedback_queue=None,
    cancel_event=None,
):
    """Execute one pipeline in an isolated spawned worker process."""
    global _worker_event_queue, _worker_cancel_event
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

    _worker_event_queue = event_queue
    _worker_cancel_event = cancel_event
    run_id = config.get("_run_id")
    if run_id:
        _project_runs[project_id] = run_id

    # Keep the existing multiline_input implementation inside the worker, and
    # relay feedback/cancellation from process-safe IPC into its local Event.
    from util.util import (
        cancel_feedback_slot,
        register_feedback_slot,
        set_stream_callback,
        submit_feedback,
        unregister_feedback_slot,
    )
    register_feedback_slot(project_id)
    set_stream_callback(_emit)

    def _feedback_relay():
        if feedback_queue is None:
            return
        while True:
            try:
                value = feedback_queue.get()
            except (EOFError, OSError):
                cancel_feedback_slot(project_id)
                return
            if value == "__CANCEL__":
                cancel_feedback_slot(project_id)
                return
            submit_feedback(project_id, value)

    feedback_thread = threading.Thread(
        target=_feedback_relay,
        name=f"reagent-feedback-{project_id}",
        daemon=True,
    )
    feedback_thread.start()

    _update_project_status_sync(
        project_id,
        status="running",
        current_stage="meta_analysis",
        current_crew=None,
    )

    # --- Set per-run output directory (process-isolated) ---
    # Use relative path (relative to cwd which is project_root) because
    # CrewAI's output_file concatenates cwd + output_file path
    from util.util import set_store_path
    project_output = (
        os.path.join("experiment", project_id, "runs", run_id)
        if run_id
        else os.path.join("experiment", project_id)
    )
    set_store_path(project_output)
    os.environ["REAGENT_RUN_ID"] = run_id or project_id
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

    # Register LLM stream chunk listener for token-level SSE events
    from crewai.events.event_bus import crewai_event_bus
    from crewai.events.types.llm_events import LLMStreamChunkEvent

    _current_crew_name = [None]  # mutable ref for closure

    def _on_llm_chunk(source, event):
        """Forward LLM stream chunks as SSE 'token' events."""
        if not isinstance(event, LLMStreamChunkEvent):
            return
        chunk_text = event.chunk if hasattr(event, "chunk") else ""
        if not chunk_text:
            return
        agent_role = event.agent_role if hasattr(event, "agent_role") else None
        _emit(project_id, "token",
              delta=chunk_text,
              crew_name=_current_crew_name[0],
              agent_role=agent_role)

    crewai_event_bus.register_handler(LLMStreamChunkEvent, _on_llm_chunk)

    # Register run_with_retry event hooks inside this isolated process.
    from util import run_with_retry  # noqa: F401
    import util as util_mod

    _original_run_with_retry = util_mod.run_with_retry

    def _patched_run_with_retry(crew_callable, inputs, name, retries=5,
                                delay=15, post_process_callable=None,
                                post_process_params=None):
        # Cancel check: if the project has been marked for cancellation,
        # abort before starting the next crew.
        with _cancel_lock:
            cancelled = project_id in _cancelled_projects
        if _worker_cancel_event is not None:
            cancelled = cancelled or _worker_cancel_event.is_set()
        if cancelled:
            from util.util import PipelineCancelledError
            raise PipelineCancelledError(
                f"Pipeline for project {project_id} was cancelled"
            )

        _current_crew_name[0] = name  # track for token events

        _update_project_status_sync(
            project_id,
            status="running",
            current_stage=config.get("_current_stage", ""),
            current_crew=name,
        )
        event_fields = _crew_event_fields(name)
        _emit(
            project_id,
            "crew_start",
            crew_name=name,
            stage=config.get("_current_stage", ""),
            **event_fields,
        )
        try:
            result = _original_run_with_retry(
                crew_callable, inputs, name, retries, delay,
                post_process_callable, post_process_params,
            )
            _update_project_status_sync(project_id, current_crew=None)
            completion_type = (
                "artifact_complete"
                if event_fields["produces_artifact"]
                else "crew_complete"
            )
            _emit(
                project_id,
                completion_type,
                crew_name=name,
                stage=config.get("_current_stage", ""),
                **event_fields,
            )
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
        _emit(
            project_id,
            "artifact_complete",
            crew_name="BRD",
            stage="business_requirements",
            **_artifact_event_fields("BRD"),
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

        # A run id is normally unique, but remove any stale proof before SRS
        # starts so recovery can only accept this execution's final commit.
        (
            Path(project_output) / ".pipeline" / "srs_complete.json"
        ).unlink(missing_ok=True)

        # 必须使用包路径；仓库根目录也有 main.py（统一启动脚本），
        # ``from main`` 会错误导入该文件并导致 ImportError。
        from reagent.main import RequirementSpecificationrun
        RequirementSpecificationrun(
            document_template=doc_template,
            document_skeleton=doc_skeleton,
            doc_content=doc_planning,
            chapter_dependence=ch_dep,
            SRS_Reference=art_plan,
            srs_example_path=srs_example_path,
        )
        _emit(
            project_id,
            "artifact_complete",
            crew_name="SRS",
            stage="srs_generation",
            **_artifact_event_fields("SRS"),
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
        from util.util import PipelineCancelledError, PipelineInterruptTimeoutError

        if isinstance(e, PipelineCancelledError):
            # Pipeline was cancelled (project deleted or manual cancel)
            _update_project_status_sync(
                project_id,
                status="cancelled",
                current_stage=None,
                current_crew=None,
            )
            _emit(project_id, "cancelled", wait=True,
                  reason="Project was deleted or manually cancelled")

        elif isinstance(e, PipelineInterruptTimeoutError):
            # Interrupt wait timed out
            _update_project_status_sync(
                project_id,
                status="error",
                current_stage=config.get("_current_stage"),
                current_crew=None,
                last_error=f"Interrupt timeout: {e}",
            )
            _emit(project_id, "error", wait=True,
                  error=f"Interrupt wait timed out: {e}",
                  recoverable=False)

        else:
            # Generic error — original logic
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
        unregister_feedback_slot(project_id)
        with _cancel_lock:
            _cancelled_projects.discard(project_id)
        # Restore original run_with_retry
        util_mod.run_with_retry = _original_run_with_retry
        # Unregister LLM chunk listener
        try:
            with crewai_event_bus._rwlock.w_locked():
                handlers = crewai_event_bus._sync_handlers.get(LLMStreamChunkEvent, frozenset())
                crewai_event_bus._sync_handlers[LLMStreamChunkEvent] = handlers - {_on_llm_chunk}
        except Exception:
            pass
        if _worker_event_queue is not None:
            _worker_event_queue.put({"type": "__worker_done__"})
        _project_runs.pop(project_id, None)
        _worker_event_queue = None
        _worker_cancel_event = None
