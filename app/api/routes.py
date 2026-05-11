"""API routes for research endpoints."""

from fastapi import APIRouter
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
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/status")
async def status():
    """Status endpoint."""
    return {"status": "API ready"}


@router.post("/enhance-prompt")
async def enhance_prompt(request: PromptEnhancementRequest):
    """
    Enhance and structure user prompt.

    Args:
        request: Prompt enhancement request with user prompt

    Returns:
        Enhanced prompt with structured data
    """
    logger.info(f"Enhancing prompt: {request.prompt[:60]}...")
    clarifier = get_prompt_clarifier()
    enhanced = await clarifier.enhance_prompt(request.prompt)
    return enhanced


@router.post("/plan-research")
async def plan_research(request: PlanningRequest):
    """
    Create research execution plan.

    Args:
        request: Planning request with enhanced prompt

    Returns:
        List of research tasks
    """
    logger.info(f"Planning research for {len(request.enhanced_prompt.topics)} topics")
    planner = get_planner()
    tasks = await planner.create_plan(request.enhanced_prompt)
    return {"tasks": tasks}


@router.post("/execute-research")
async def execute_research(request: ExecutionRequest):
    """
    Execute research tasks concurrently.

    Args:
        request: Execution request with tasks

    Returns:
        List of task results
    """
    logger.info(f"Executing {len(request.tasks)} research tasks")
    worker = get_worker()
    results = await worker.execute_tasks(request.tasks)
    return {"results": results}


@router.post("/format-report")
async def format_report(request: FormattingRequest):
    """
    Format research results into professional report.

    Args:
        request: Formatting request with task results

    Returns:
        Formatted research report
    """
    logger.info(f"Formatting research report...")
    formatter = get_formatter()
    report = await formatter.format_report(
        request.task_results,
        request.enhanced_prompt,
    )
    return report


@router.post("/research", response_model=FullResearchResponse)
async def run_full_research(request: FullResearchRequest) -> FullResearchResponse:
    """
    Execute complete end-to-end research pipeline.

    Args:
        request: Full research request with user prompt

    Returns:
        Full research response with report and file path
    """
    logger.info(f"Starting full research pipeline for: {request.prompt[:60]}...")
    orchestrator = get_orchestrator()
    response = await orchestrator.run_research_pipeline(request.prompt)
    return response
