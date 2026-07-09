"""API routes for research endpoints."""

from fastapi import APIRouter, Request
from app.models.schemas import (
    PromptEnhancementRequest,
    PlanningRequest,
    ExecutionRequest,
    FormattingRequest,
    FullResearchRequest,
    FullResearchResponse,
)
from app.agents.prompt_enhancer import get_prompt_clarifier
from app.agents.planner import get_planner
from app.agents.worker import get_worker
from app.agents.formatter import get_formatter
from app.services.orchestration import get_orchestrator
from app.graph.tracker import PipelabTracker
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


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


@router.post("/research", response_model=FullResearchResponse)
async def run_full_research(request: FullResearchRequest) -> FullResearchResponse:
    """Execute complete end-to-end research pipeline via LangGraph."""
    logger.info(f"Starting full research pipeline for: {request.prompt[:60]}...")
    orchestrator = get_orchestrator()
    response = await orchestrator.run_research_pipeline(request.prompt)
    return response