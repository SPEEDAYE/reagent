"""Terminal progress reporting for CLI, scripts, and experiment runs."""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field


@dataclass
class TerminalProgress:
    run_id: str | None = None
    model: str | None = None
    output_path: str | None = None
    started_at: float = field(default_factory=time.time)

    @classmethod
    def from_env(cls) -> "TerminalProgress":
        return cls(
            run_id=os.getenv("REAGENT_RUN_ID"),
            model=os.getenv("REAGENT_MODEL_ID"),
            output_path=os.getenv("REAGENT_OUTPUT_PATH"),
        )

    def update(self, stage: str, message: str, *, current: int | None = None, total: int | None = None) -> None:
        elapsed = round(time.time() - self.started_at, 2)
        payload = {
            "stage": stage,
            "message": message,
            "run_id": self.run_id,
            "model": self.model,
            "output_path": self.output_path,
            "elapsed_seconds": elapsed,
        }
        if current is not None and total is not None:
            payload["current"] = current
            payload["total"] = total
        if sys.stdout.isatty():
            prefix = f"[{stage}]"
            detail = f" ({current}/{total})" if current is not None and total is not None else ""
            print(f"{prefix}{detail} {message} | run={self.run_id} | output={self.output_path}", flush=True)
        else:
            print(json.dumps({"type": "progress", **payload}, ensure_ascii=False), flush=True)
