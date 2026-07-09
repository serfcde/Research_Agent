"""
Main orchestration service.

CHANGED (LangGraph refactor):
  - ResearchOrchestrator.run_research_pipeline() now invokes the compiled
    LangGraph instead of calling agents directly.
  - All agent logic is unchanged; only the calling convention is different.
  - PipelabTracker is injected into the graph state so every node emits
    structured execution events to logs/pipelab_trace.jsonl.

Public API is identical to the original — callers (api/routes.py) require
no modification.
"""

import time
from app.graph.graph import get_research_graph
from app.graph.tracker import new_tracker
from app.models.schemas import FullResearchResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResearchOrchestrator:
    """
    Orchestrator for the end-to-end research pipeline.

    The pipeline is now implemented as a LangGraph StateGraph:

      prompt_enhancer → planner → worker → formatter

    Each node wraps the corresponding agent class (unchanged) and
    emits Pipelab tracking events at its start and end boundaries.
    """

    async def run_research_pipeline(self, user_prompt: str) -> FullResearchResponse:
        """
        Run the complete research pipeline.

        Args:
            user_prompt: Raw user research prompt.

        Returns:
            FullResearchResponse with the report and saved file path.
        """
        pipeline_start = time.time()

        logger.info("=" * 80)
        logger.info(f"[Graph] Starting research pipeline: {user_prompt[:80]}...")
        logger.info("=" * 80)

        # Create a Pipelab tracker for this run and emit run_start
        tracker = new_tracker()
        tracker.emit_run_start(user_prompt)

        try:
            graph = get_research_graph()

            # Initial state — tracker is passed as a private key so nodes
            # can emit events without it appearing in the public schema.
            initial_state = {
                "user_prompt": user_prompt,
                "_tracker": tracker,
                "execution_events": [],
            }

            # Invoke the graph; LangGraph merges each node's return dict
            # into the accumulated state automatically.
            final_state = await graph.ainvoke(initial_state)

            pipeline_time = time.time() - pipeline_start
            tracker.emit_run_end(total_seconds=pipeline_time, status="completed")

            logger.info("=" * 80)
            logger.info(f"[Graph] Pipeline completed in {pipeline_time:.1f}s")
            logger.info("=" * 80)

            return FullResearchResponse(
                report=final_state["report"],
                file_path=final_state["file_path"],
                status="completed",
                total_execution_time_seconds=pipeline_time,
            )

        except Exception as exc:
            pipeline_time = time.time() - pipeline_start
            tracker.emit_run_end(total_seconds=pipeline_time, status="failed")

            logger.error(f"[Graph] Pipeline failed after {pipeline_time:.1f}s: {exc}")
            logger.exception("Full traceback:")
            raise


# ---------------------------------------------------------------------------
# Singleton helpers (unchanged API)
# ---------------------------------------------------------------------------

_orchestrator = None


def get_orchestrator() -> ResearchOrchestrator:
    """Return the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ResearchOrchestrator()
        logger.info("Research orchestrator initialised (LangGraph backend)")
    return _orchestrator