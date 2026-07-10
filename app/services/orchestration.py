"""
Main orchestration service.

The pipeline is a LangGraph StateGraph with a critic-driven replanning
loop (see app/graph/graph.py). Two entry points:

  run_research_pipeline(prompt, run_id)  — awaitable, returns the report.
  run_research_background(run_id, prompt) — fire-and-forget coroutine used
      by POST /research: executes the pipeline, records the outcome in the
      run store, and streams node events to SSE subscribers via the
      PipelabTracker (run_id doubles as the LangGraph thread_id, so with
      Postgres checkpointing configured the run state is durable).
"""

import asyncio
import time

from app.graph.graph import get_research_graph
from app.graph.tracker import PipelabTracker, new_tracker
from app.models.schemas import FullResearchResponse
from app.services.llm_service import start_usage_tracking
from app.services.run_store import get_run_store
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Keep references to resume tasks so they aren't garbage-collected.
_resume_tasks: set = set()


class ResearchOrchestrator:
    """Orchestrator for the end-to-end research pipeline."""

    async def run_research_pipeline(
        self,
        user_prompt: str,
        run_id: str | None = None,
        tracker: PipelabTracker | None = None,
    ) -> FullResearchResponse:
        """
        Run the complete research pipeline.

        Args:
            user_prompt: Raw user research prompt.
            run_id: Stable run identifier; doubles as the checkpointer
                thread_id. Generated when omitted.
            tracker: Event tracker; created from run_id when omitted.

        Returns:
            FullResearchResponse with the report and saved file path.
        """
        pipeline_start = time.time()

        if tracker is None:
            tracker = PipelabTracker(run_id) if run_id else new_tracker()
        run_id = run_id or tracker.run_id

        logger.info("=" * 80)
        logger.info(f"[Graph] Starting research pipeline ({run_id}): {user_prompt[:80]}...")
        logger.info("=" * 80)

        tracker.emit_run_start(user_prompt)
        usage = start_usage_tracking()

        try:
            graph = await get_research_graph()

            config = {
                "configurable": {
                    "thread_id": run_id,
                    "tracker": tracker,
                }
            }

            final_state = await graph.ainvoke({"user_prompt": user_prompt}, config=config)

            pipeline_time = time.time() - pipeline_start
            tracker.emit_run_end(total_seconds=pipeline_time, status="completed", usage=usage)

            logger.info("=" * 80)
            logger.info(f"[Graph] Pipeline completed in {pipeline_time:.1f}s ({run_id})")
            logger.info("=" * 80)

            return FullResearchResponse(
                report=final_state["report"],
                file_path=final_state["file_path"],
                status="completed",
                total_execution_time_seconds=pipeline_time,
            )

        except Exception as exc:
            pipeline_time = time.time() - pipeline_start
            tracker.emit_run_end(total_seconds=pipeline_time, status="failed", usage=usage)

            logger.error(f"[Graph] Pipeline failed after {pipeline_time:.1f}s: {exc}")
            logger.exception("Full traceback:")
            raise

    async def run_research_background(self, run_id: str, user_prompt: str) -> None:
        """
        Background-job wrapper: run the pipeline and record the outcome
        in the run store. Never raises — failures are persisted.
        """
        store = get_run_store()
        try:
            response = await self.run_research_pipeline(user_prompt, run_id=run_id)
            await store.mark_completed(run_id, response.model_dump(mode="json"))
        except Exception as exc:
            logger.error(f"Background run {run_id} failed: {exc}")
            try:
                await store.mark_failed(run_id, str(exc))
            except Exception as store_exc:
                logger.error(f"Could not record failure for run {run_id}: {store_exc}")

    async def resume_interrupted_runs(self) -> int:
        """
        Crash recovery: pick up runs left in 'running' by a previous
        process and resume them from their last LangGraph checkpoint
        (or restart them when no checkpoint was written yet).

        Returns the number of runs scheduled for resumption.
        """
        store = get_run_store()
        try:
            runs = await store.list_runs(limit=100)
        except Exception as exc:
            logger.warning(f"Resume scan failed: {exc}")
            return 0

        interrupted = [run for run in runs if run["status"] == "running"]
        for run in interrupted:
            logger.info(f"Resuming interrupted run {run['id']} from checkpoint")
            task = asyncio.create_task(self._resume_run(run["id"], run["prompt"]))
            _resume_tasks.add(task)
            task.add_done_callback(_resume_tasks.discard)
        return len(interrupted)

    async def _resume_run(self, run_id: str, user_prompt: str) -> None:
        """Resume one interrupted run; falls back to a fresh start."""
        store = get_run_store()
        pipeline_start = time.time()
        tracker = PipelabTracker(run_id)

        try:
            graph = await get_research_graph()
            config = {"configurable": {"thread_id": run_id, "tracker": tracker}}

            checkpoint_state = None
            try:
                checkpoint_state = await graph.aget_state(config)
            except Exception:
                pass  # no checkpointer configured

            usage = start_usage_tracking()
            if checkpoint_state and checkpoint_state.next:
                # Invoking with None input continues from the checkpoint.
                logger.info(f"Run {run_id}: resuming at node(s) {checkpoint_state.next}")
                final_state = await graph.ainvoke(None, config=config)
            else:
                logger.info(f"Run {run_id}: no usable checkpoint, restarting pipeline")
                tracker.emit_run_start(user_prompt)
                final_state = await graph.ainvoke({"user_prompt": user_prompt}, config=config)

            pipeline_time = time.time() - pipeline_start
            tracker.emit_run_end(total_seconds=pipeline_time, status="completed", usage=usage)

            response = FullResearchResponse(
                report=final_state["report"],
                file_path=final_state["file_path"],
                status="completed",
                total_execution_time_seconds=pipeline_time,
            )
            await store.mark_completed(run_id, response.model_dump(mode="json"))
            logger.info(f"Run {run_id} resumed and completed in {pipeline_time:.1f}s")

        except Exception as exc:
            tracker.emit_run_end(total_seconds=time.time() - pipeline_start, status="failed")
            logger.error(f"Resume of run {run_id} failed: {exc}")
            try:
                await store.mark_failed(run_id, f"Resume failed: {exc}")
            except Exception as store_exc:
                logger.error(f"Could not record resume failure for {run_id}: {store_exc}")


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------

_orchestrator = None


def get_orchestrator() -> ResearchOrchestrator:
    """Return the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ResearchOrchestrator()
        logger.info("Research orchestrator initialised (LangGraph backend)")
    return _orchestrator
