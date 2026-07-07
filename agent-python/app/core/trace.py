from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


def new_trace_id() -> str:
    return str(uuid.uuid4())


class TraceRecorder:
    """Records node-level execution details to a JSON trace file."""

    def __init__(self, trace_id: str | None = None, trace_dir: str | Path | None = None):
        self.trace_id = trace_id or new_trace_id()
        self.trace_dir = Path(trace_dir or settings.trace_dir)
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: datetime | None = None
        self.events: list[dict[str, Any]] = []

    def start_node(self, node_name: str, input_summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "node_name": node_name,
            "started_at": datetime.now(timezone.utc),
            "started_perf": time.perf_counter(),
            "input_summary": input_summary,
        }

    def finish_node(
        self,
        span: dict[str, Any],
        output_summary: dict[str, Any],
        error: str | None = None,
        llm_model: str | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        self.events.append(
            {
                "trace_id": self.trace_id,
                "node_name": span["node_name"],
                "started_at": span["started_at"].isoformat(),
                "finished_at": finished_at.isoformat(),
                "input_summary": span["input_summary"],
                "output_summary": output_summary,
                "latency_ms": round((time.perf_counter() - span["started_perf"]) * 1000, 2),
                "error": error,
                "llm_model": llm_model,
                "token_usage": token_usage,
            }
        )

    def save(self) -> str:
        self.finished_at = datetime.now(timezone.utc)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        path = self.trace_dir / f"{self.trace_id}.json"
        payload = {
            "trace_id": self.trace_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "events": self.events,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
