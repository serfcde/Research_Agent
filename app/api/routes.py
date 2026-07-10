"""API routes for research endpoints."""

import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.schemas import (
    PromptEnhancementRequest,
    PlanningRequest,
    ExecutionRequest,
    FormattingRequest,
    FullResearchRequest,
)
from app.agents.prompt_enhancer import get_prompt_clarifier
from app.agents.planner import get_planner
from app.agents.worker import get_worker
from app.agents.formatter import get_formatter
from app.services.orchestration import get_orchestrator
from app.services.run_store import get_run_store
from app.graph import tracker as tracker_bus
from app.graph.tracker import PipelabTracker
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Shared limiter — registered on the app in main.create_app().
limiter = Limiter(key_func=get_remote_address)

# Keep references to in-flight background tasks so they aren't GC'd.
_background_tasks: set = set()


def _tracker_from(http_request: Request) -> PipelabTracker:
    """
    Build a PipelabTracker whose run_id matches the trace_id
    the frontend sends as X-Trace-Id. This correlates every
    pipelab_trace.jsonl event with the frontend's own span tree.
    """
    # Starlette headers are case-insensitive
    trace_id = http_request.headers.get("x-trace-id")
    span_id = http_request.headers.get("x-span-id")
    tracker = PipelabTracker(run_id=trace_id or "no-trace")
    # Store span_id so node events can reference it
    tracker.current_span_id = span_id
    return tracker


@router.get("/status")
async def status():
    """Status endpoint."""
    return {"status": "API ready"}


# --------------------------------------------------------------------------- #
# Full pipeline as a durable background job                                    #
# --------------------------------------------------------------------------- #

@router.post("/research", status_code=202)
@limiter.limit("5/minute")
async def start_research(body: FullResearchRequest, request: Request):
    """
    Start the end-to-end research pipeline as a background job.

    Returns immediately with 202 and a run_id. Progress can be observed
    on GET /research/{run_id} (polling) or GET /research/{run_id}/events
    (SSE stream of node transitions). The X-Trace-Id header, when present,
    becomes the run_id so frontend spans correlate with backend events.
    """
    run_id = request.headers.get("x-trace-id") or f"run_{uuid.uuid4().hex[:12]}"
    logger.info(f"Starting research run {run_id}: {body.prompt[:60]}...")

    store = get_run_store()
    existing = await store.get_run(run_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Run {run_id} already exists")
    await store.create_run(run_id, body.prompt)

    orchestrator = get_orchestrator()
    task = asyncio.create_task(orchestrator.run_research_background(run_id, body.prompt))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"run_id": run_id, "status": "running"}


@router.get("/research/{run_id}")
async def get_research_run(run_id: str):
    """Get the current status (and report, when finished) of a run."""
    run = await get_run_store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.get("/runs")
async def list_research_runs(limit: int = 50):
    """List recent runs, newest first (without report bodies)."""
    return {"runs": await get_run_store().list_runs(limit=min(limit, 200))}


@router.get("/research/{run_id}/events")
async def stream_research_events(run_id: str, http_request: Request):
    """
    SSE stream of tracker events (run_start, node_start, node_end, run_end)
    for a run. Replays events already emitted, then streams live ones.
    """
    store = get_run_store()
    run = await store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    async def event_stream():
        # Subscribe BEFORE replaying so no live event is missed; replayed
        # and queued events are deduped on (event_type, node, ts).
        queue = tracker_bus.subscribe(run_id)
        seen = set()
        try:
            for event in tracker_bus.read_run_events(run_id):
                seen.add((event["event_type"], event["node"], event["ts"]))
                yield f"data: {json.dumps(event)}\n\n"
                if event["event_type"] == "run_end":
                    return

            # Run already finished but produced no run_end in the trace
            # (e.g. trace file rotated): fall back to the stored status.
            current = await store.get_run(run_id)
            if current and current["status"] in ("completed", "failed"):
                yield f"data: {json.dumps({'event_type': 'run_end', 'node': 'orchestrator', 'run_id': run_id, 'ts': None, 'data': {'status': current['status']}})}\n\n"
                return

            while True:
                if await http_request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if event.get("event_type") == "__stream_end__":
                    return
                key = (event["event_type"], event["node"], event["ts"])
                if key in seen:
                    continue
                yield f"data: {json.dumps(event)}\n\n"
                if event["event_type"] == "run_end":
                    return
        finally:
            tracker_bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------- #
# Per-step endpoints (used by tests and for debugging individual agents)       #
# --------------------------------------------------------------------------- #

@router.post("/enhance-prompt")
async def enhance_prompt(request: PromptEnhancementRequest, http_request: Request):
    """Enhance and structure user prompt."""
    tracker = _tracker_from(http_request)
    logger.info(f"Enhancing prompt: {request.prompt[:60]}...")

    start_ts = tracker.emit_node_start(
        "prompt_enhancer",
        input_summary={"prompt": request.prompt[:120]},
    )
    try:
        clarifier = get_prompt_clarifier()
        enhanced = await clarifier.enhance_prompt(request.prompt)
        tracker.emit_node_end(
            "prompt_enhancer", start_ts,
            output_summary={"topics": enhanced.topics, "depth": enhanced.research_depth},
        )
        return enhanced
    except Exception as exc:
        tracker.emit_node_end("prompt_enhancer", start_ts, error=str(exc))
        raise


@router.post("/plan-research")
async def plan_research(request: PlanningRequest, http_request: Request):
    """Create research execution plan."""
    tracker = _tracker_from(http_request)
    logger.info(f"Planning research for {len(request.enhanced_prompt.topics)} topics")

    start_ts = tracker.emit_node_start(
        "planner",
        input_summary={"topics": request.enhanced_prompt.topics},
    )
    try:
        planner = get_planner()
        tasks = await planner.create_plan(request.enhanced_prompt)
        tracker.emit_node_end(
            "planner", start_ts,
            output_summary={"task_count": len(tasks)},
        )
        return {"tasks": tasks}
    except Exception as exc:
        tracker.emit_node_end("planner", start_ts, error=str(exc))
        raise


@router.post("/execute-research")
async def execute_research(request: ExecutionRequest, http_request: Request):
    """Execute research tasks concurrently."""
    tracker = _tracker_from(http_request)
    logger.info(f"Executing {len(request.tasks)} research tasks")

    start_ts = tracker.emit_node_start(
        "worker",
        input_summary={"task_count": len(request.tasks)},
    )
    try:
        worker = get_worker()
        results = await worker.execute_tasks(request.tasks)
        completed = sum(1 for r in results if r.status == "completed")
        tracker.emit_node_end(
            "worker", start_ts,
            output_summary={"total": len(results), "completed": completed},
        )
        return {"results": results}
    except Exception as exc:
        tracker.emit_node_end("worker", start_ts, error=str(exc))
        raise


@router.post("/format-report")
async def format_report(request: FormattingRequest, http_request: Request):
    """Format research results into professional report."""
    tracker = _tracker_from(http_request)
    logger.info("Formatting research report...")

    start_ts = tracker.emit_node_start(
        "formatter",
        input_summary={"result_count": len(request.task_results)},
    )
    try:
        formatter = get_formatter()
        report = await formatter.format_report(
            request.task_results,
            request.enhanced_prompt,
        )
        tracker.emit_node_end(
            "formatter", start_ts,
            output_summary={"total_words": report.total_words, "citations": len(report.citations)},
        )
        return report
    except Exception as exc:
        tracker.emit_node_end("formatter", start_ts, error=str(exc))
        raise
