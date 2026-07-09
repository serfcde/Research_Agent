"""
Pipelab execution tracker.

Emits structured JSON events at each node boundary so the Pipelab
dashboard can reconstruct the full execution graph:

  node_start  →  node_end  (for each of the 4 agent nodes)

Each event is appended to logs/pipelab_trace.jsonl so the frontend
lib/server/trace.ts can ingest it alongside the existing debug.log.
No external SDK is required — Pipelab ingests the JSONL file via the
existing Pipelock monitoring infrastructure.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Trace log path — sibling to the existing debug.log / error.log
_TRACE_PATH = Path("logs/pipelab_trace.jsonl")


def _ensure_log_dir() -> None:
    _TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _write_event(event: dict) -> None:
    """Append a single JSON event to the trace file."""
    try:
        _ensure_log_dir()
        with _TRACE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
    except Exception as exc:
        logger.warning(f"PipelabTracker: could not write event — {exc}")


class PipelabTracker:
    """
    Lightweight span tracker that emits node-level events.

    Usage (inside a LangGraph node function):

        tracker = PipelabTracker(run_id)
        with tracker.span("prompt_enhancer", state):
            result = await agent.enhance_prompt(state["user_prompt"])
    """

    def __init__(self, run_id: str):
        self.run_id = run_id

    # ------------------------------------------------------------------ #
    # Public helpers                                                       #
    # ------------------------------------------------------------------ #

    def emit_run_start(self, user_prompt: str) -> None:
        self._emit(
            event_type="run_start",
            node="orchestrator",
            data={"user_prompt": user_prompt[:200]},
        )

    def emit_node_start(self, node: str, input_summary: Optional[dict] = None) -> float:
        """Emit a node_start event and return the start timestamp."""
        start_ts = time.time()
        self._emit(
            event_type="node_start",
            node=node,
            data={"input": input_summary or {}},
            ts=start_ts,
        )
        logger.debug(f"[Pipelab] node_start  → {node}")
        return start_ts

    def emit_node_end(
        self,
        node: str,
        start_ts: float,
        output_summary: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """Emit a node_end event with duration and optional output summary."""
        duration_ms = round((time.time() - start_ts) * 1000, 1)
        self._emit(
            event_type="node_end",
            node=node,
            data={
                "output": output_summary or {},
                "duration_ms": duration_ms,
                "error": error,
            },
        )
        status = "error" if error else "ok"
        logger.debug(f"[Pipelab] node_end    ← {node}  ({duration_ms} ms, {status})")

    def emit_run_end(self, total_seconds: float, status: str = "completed") -> None:
        self._emit(
            event_type="run_end",
            node="orchestrator",
            data={"total_seconds": round(total_seconds, 2), "status": status},
        )

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _emit(
        self,
        event_type: str,
        node: str,
        data: Any = None,
        ts: Optional[float] = None,
    ) -> None:
        event = {
            "run_id": self.run_id,
            "event_type": event_type,
            "node": node,
            "ts": ts or time.time(),
            "data": data or {},
        }
        _write_event(event)


def new_tracker() -> PipelabTracker:
    """Create a tracker with a fresh UUID run ID."""
    return PipelabTracker(run_id=str(uuid.uuid4()))
