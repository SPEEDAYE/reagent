# backend/services/stream_manager.py — Per-project SSE event bridge with
# reconnection support via event history buffer.
#
# Outline:
#   StreamManager
#     set_loop(loop)                capture main event loop at startup
#     create_queue(pid)             create asyncio.Queue + history buffer
#     remove_queue(pid)             tear down queue (history kept until TTL)
#     has_queue(pid)
#     publish(pid, event) async     put event on queue AND append to history
#     publish_sync(pid, event)      thread-safe variant for worker threads
#     subscribe(pid,                SSE generator. Behavior:
#                last_event_id=None) - If last_event_id given: replay missed
#                                      events from history, then live-stream
#                                    - If no queue but history exists: replay
#                                      full history, then wait on a new queue
#                                    - If nothing known about pid: error event
#     _prune_history(pid)           TTL-based history cleanup (called lazily)
#
#   Event IDs: monotonically increasing int per-project, injected as the
#   "_seq" field on every event. Exposed in the SSE "id:" line so that the
#   browser's native EventSource sets Last-Event-ID on reconnect.
#
#   Retention: history keeps the last MAX_HISTORY events per project and
#   drops them HISTORY_TTL_SECONDS after the pipeline finishes.
#
#   stream_manager                module-level singleton.
import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone
from backend.services.event_service import EventService

# --- Configuration ---------------------------------------------------------
MAX_HISTORY = 500            # keep at most N events per project (memory cap)
HISTORY_TTL_SECONDS = 3600   # drop history 1h after pipeline terminates
event_svc = EventService()


class StreamManager:
    """Manages per-project SSE event queues with reconnection-safe history.

    Workers publish events from sync threads via ``publish_sync``;
    the SSE endpoint consumes via ``subscribe`` (async generator) and can
    resume after disconnects by providing the last seen event id.
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        # Per-project ring buffer of published events (with _seq ids).
        self._history: dict[str, deque] = {}
        # Per-project sequence counter for event ids.
        self._seq: dict[str, int] = {}
        # Per-project terminal timestamp (for TTL-based cleanup).
        self._terminated_at: dict[str, float] = {}
        self._run_ids: dict[str, str] = {}

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    # -- queue lifecycle -------------------------------------------------

    def create_queue(self, project_id: str, run_id: str | None = None):
        """Idempotent: creates queue + history if missing."""
        self._prune_expired_history()
        # A project may run repeatedly. A new run must never inherit the prior
        # run's in-memory sequence or replay buffer.
        if run_id and self._run_ids.get(project_id) != run_id:
            self._queues[project_id] = asyncio.Queue()
            self._history[project_id] = deque(maxlen=MAX_HISTORY)
            self._seq[project_id] = 0
            self._run_ids[project_id] = run_id
        if project_id not in self._queues:
            self._queues[project_id] = asyncio.Queue()
        if project_id not in self._history:
            self._history[project_id] = deque(maxlen=MAX_HISTORY)
            self._seq[project_id] = 0
        # Drop any prior "terminated" marker — session is being restarted.
        self._terminated_at.pop(project_id, None)

    def remove_queue(self, project_id: str):
        """Remove the live queue but keep history for reconnection window."""
        self._queues.pop(project_id, None)
        # Mark terminated so history gets TTL-dropped later.
        self._terminated_at[project_id] = time.time()

    def has_queue(self, project_id: str) -> bool:
        return project_id in self._queues

    def has_history(self, project_id: str) -> bool:
        return project_id in self._history and len(self._history[project_id]) > 0

    # -- publish (async) -------------------------------------------------

    async def publish(self, project_id: str, event: dict):
        """Append to history and (if queue exists) push to live consumers."""
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
        # Assign a monotonically increasing id for reconnection replay.
        self._seq.setdefault(project_id, 0)
        self._seq[project_id] += 1
        event["_seq"] = self._seq[project_id]

        # Record in history even if no live consumer right now.
        if project_id not in self._history:
            self._history[project_id] = deque(maxlen=MAX_HISTORY)
        self._history[project_id].append(event)

        # Persist lifecycle events for replay after backend restarts. Token
        # chunks intentionally remain ephemeral to keep storage bounded.
        try:
            await event_svc.persist(event)
        except Exception as exc:
            # Event persistence must not stop a running LLM pipeline. The
            # in-memory stream remains available and the failure is observable.
            print(f"[stream] Failed to persist event: {exc}")

        # Mark terminated on final events so TTL cleanup can run.
        if event.get("type") in ("finished", "cancelled") or (
            event.get("type") == "error" and not event.get("recoverable", False)
        ):
            self._terminated_at[project_id] = time.time()

        queue = self._queues.get(project_id)
        if queue:
            await queue.put(event)

    # -- publish from sync thread ----------------------------------------

    def publish_sync(self, project_id: str, event: dict):
        """Thread-safe publish: schedule coroutine on the main event loop.

        Returns the scheduled future so callers that are about to tear down a
        live queue can wait until the event has actually been delivered.
        """
        if self._loop is None:
            return None
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
        return asyncio.run_coroutine_threadsafe(
            self.publish(project_id, event), self._loop
        )

    # -- subscribe (async generator for SSE) -----------------------------

    async def subscribe(self, project_id: str, last_event_id: int | None = None):
        """SSE generator with reconnection support.

        :param project_id: target project
        :param last_event_id: if provided, replay events with _seq > this value
        """
        self._prune_expired_history()

        history = self._history.get(project_id)
        queue = self._queues.get(project_id)

        # Case: genuinely unknown project_id → error and close.
        if not queue and not history:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"type": "error",
                     "error": "No active session for this project",
                     "project_id": project_id},
                    ensure_ascii=False,
                ),
            }
            return

        # Always announce the connection first. Frontend uses this to render
        # the "connected" indicator and to learn the current event id floor.
        yield {
            "event": "connected",
            "data": json.dumps(
                {"type": "connected",
                 "project_id": project_id,
                 "resume": last_event_id is not None,
                 "last_event_id": last_event_id or 0},
                ensure_ascii=False,
            ),
        }

        # Replay history past last_event_id. If last_event_id is None and the
        # queue is gone (e.g. server restarted mid-pipeline), replay ALL
        # history so the client can resync.
        replay_from = last_event_id if last_event_id is not None else 0
        if history:
            for event in list(history):
                if event.get("_seq", 0) > replay_from:
                    raw_type = event.get("type", "message")
                    event_type = raw_type if isinstance(raw_type, str) else "message"
                    yield {
                        "event": event_type,
                        "id": str(event.get("_seq", "")),
                        "data": json.dumps(event, ensure_ascii=False),
                    }

        # If the pipeline is done, don't hang — close the connection.
        if not queue:
            return

        # Live-stream new events.
        while True:
            event = await queue.get()
            raw_type = event.get("type", "message")
            event_type = raw_type if isinstance(raw_type, str) else "message"
            yield {
                "event": event_type,
                "id": str(event.get("_seq", "")),
                "data": json.dumps(event, ensure_ascii=False),
            }
            if event_type in ("finished", "error", "cancelled"):
                if not event.get("recoverable", False):
                    break

    # -- history TTL cleanup ---------------------------------------------

    def _prune_expired_history(self):
        """Drop history for projects that finished more than TTL ago."""
        now = time.time()
        expired = [
            pid for pid, t in self._terminated_at.items()
            if now - t > HISTORY_TTL_SECONDS
        ]
        for pid in expired:
            self._history.pop(pid, None)
            self._seq.pop(pid, None)
            self._terminated_at.pop(pid, None)
            self._run_ids.pop(pid, None)


# Singleton used by the whole app
stream_manager = StreamManager()
