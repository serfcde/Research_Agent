"""
Pipelab execution tracker.

Emits structured JSON events at each node boundary so the Pipelab
dashboard can reconstruct the full execution graph:

  run_start → (node_start → node_end)* → run_end

Each event is:
  1. appended to logs/pipelab_trace.jsonl (durable trace),
  2. published to any in-process SSE subscribers for this run
     (see subscribe()/unsubscribe()), enabling live streaming of
     node transitions to the frontend, and
  3. recorded as Prometheus metrics (app/utils/metrics.py).
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.utils import metrics
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Trace log path — sibling to the existing debug.log / error.log
_TRACE_PATH = Path("logs/pipelab_trace.jsonl")

# In-process event bus: run_id → set of subscriber queues.
_subscribers: dict[str, set[asyncio.Queue]] = {}

# Sentinel queued after run_end so subscribers know the stream is over.
STREAM_END = {"event_type": "__stream_end__"}


def subscribe(run_id: str) -> asyncio.Queue:
    """Register a queue that receives every event emitted for run_id."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(run_id, set()).add(queue)
    metrics.SSE_SUBSCRIBERS.inc()
    return queue


def unsubscribe(run_id: str, queue: asyncio.Queue) -> None:
    """Remove a subscriber queue for run_id."""
    queues = _subscribers.get(run_id)
    if queues is not None and queue in queues:
        queues.discard(queue)
        metrics.SSE_SUBSCRIBERS.dec()
        if not queues:
            _subscribers.pop(run_id, None)


def _publish(run_id: str, event: dict) -> None:
    for queue in _subscribers.get(run_id, ()):  # copy not needed: no removal here
        queue.put_nowait(event)


def read_run_events(run_id: str) -> list:
    """
    Replay all events already persisted for run_id from the JSONL trace.

    Used by the SSE endpoint so late subscribers still see the full
    node-transition history of an in-flight (or finished) run.
    """
    events = []
    try:
        with _TRACE_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("run_id") == run_id:
                    events.append(event)
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning(f"PipelabTracker: could not replay events — {exc}")
    return events


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
        start_ts = tracker.emit_node_start("planner", input_summary={...})
        ...
        tracker.emit_node_end("planner", start_ts, output_summary={...})
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.current_span_id: str | None = None

    # ------------------------------------------------------------------ #
    # Public helpers                                                      #
    # ------------------------------------------------------------------ #

    def emit_run_start(self, user_prompt: str) -> None:
        metrics.record_run_start()
        self._emit(
            event_type="run_start",
            node="orchestrator",
            data={"user_prompt": user_prompt[:200]},
        )

    def emit_node_start(self, node: str, input_summary: dict | None = None) -> float:
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
        output_summary: dict | None = None,
        error: str | None = None,
    ) -> None:
        """Emit a node_end event with duration and optional output summary."""
        duration_ms = round((time.time() - start_ts) * 1000, 1)
        metrics.record_node_end(node, duration_ms, error is not None, output_summary)
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

    def emit_run_end(
        self,
        total_seconds: float,
        status: str = "completed",
        usage: dict | None = None,
    ) -> None:
        metrics.record_run_end(total_seconds, status, usage)
        self._emit(
            event_type="run_end",
            node="orchestrator",
            data={
                "total_seconds": round(total_seconds, 2),
                "status": status,
                "usage": usage or {},
            },
        )
        _publish(self.run_id, STREAM_END)

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    def _emit(
        self,
        event_type: str,
        node: str,
        data: Any = None,
        ts: float | None = None,
    ) -> None:
        event = {
            "run_id": self.run_id,
            "event_type": event_type,
            "node": node,
            "ts": ts or time.time(),
            "data": data or {},
        }
        _write_event(event)
        _publish(self.run_id, event)


def new_tracker() -> PipelabTracker:
    """Create a tracker with a fresh UUID run ID."""
    return PipelabTracker(run_id=str(uuid.uuid4()))
