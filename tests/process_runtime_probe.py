"""Manual smoke test for Windows spawn + Manager queue IPC."""

import os

from backend.services import execution


def main():
    executor, manager = execution._get_process_runtime()
    events = manager.Queue()
    feedback = manager.Queue()
    future = executor.submit(execution._ipc_probe_worker, events, feedback)
    announced = events.get(timeout=10)
    feedback.put("accepted")
    result = future.result(timeout=10)
    assert announced["worker_pid"] == result["worker_pid"]
    assert result["worker_pid"] != os.getpid()
    assert result["feedback"] == "accepted"
    executor.shutdown(wait=True, cancel_futures=True)
    manager.shutdown()
    execution._executor = None
    execution._manager = None
    print(f"process IPC OK: parent={os.getpid()} worker={result['worker_pid']}")


if __name__ == "__main__":
    main()
