"""Main orchestration service - coordinates all agents."""

import time
from app.agents.prompt_enhancer import get_prompt_clarifier
from app.agents.planner import get_planner
from app.agents.worker import get_worker
from app.agents.formatter import get_formatter
from app.tools.file_writer import get_file_writer
from app.models.schemas import (
    FullResearchResponse,
    ResearchReport,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResearchOrchestrator:
    """Main orchestrator for end-to-end research pipeline."""

    async def run_research_pipeline(self, user_prompt: str) -> FullResearchResponse:
        """
        Run complete research pipeline.

        Args:
            user_prompt: User research prompt

        Returns:
            Full research response with report and file path
        """
        pipeline_start = time.time()
        logger.info("=" * 80)
        logger.info(f"Starting research pipeline for: {user_prompt[:80]}...")
        logger.info("=" * 80)

        try:
            # Step 1: Clarify prompt
            logger.info("\n[Step 1/5] Enhancing prompt...")
            clarifier = get_prompt_clarifier()
            enhanced_prompt = await clarifier.enhance_prompt(user_prompt)
            logger.info(f"Topics identified: {enhanced_prompt.topics}")
            logger.info(f"Research depth: {enhanced_prompt.research_depth}")

            # Step 2: Plan research
            logger.info("\n[Step 2/5] Creating research plan...")
            planner = get_planner()
            tasks = await planner.create_plan(enhanced_prompt)
            logger.info(f"Created {len(tasks)} research tasks")

            # Step 3: Execute tasks
            logger.info(f"\n[Step 3/5] Executing {len(tasks)} tasks (concurrently)...")
            worker = get_worker()
            task_results = await worker.execute_tasks(tasks)

            # Count results
            completed = sum(1 for r in task_results if r.status == "completed")
            logger.info(f"Task execution complete: {completed}/{len(task_results)} successful")

            # Step 4: Format report
            logger.info("\n[Step 4/5] Formatting research report...")
            formatter = get_formatter()
            report = await formatter.format_report(task_results, enhanced_prompt)
            logger.info(f"Report formatted: {report.total_words} words")

            # Step 5: Save report
            logger.info("\n[Step 5/5] Saving report to file...")
            file_writer = get_file_writer()
            report_text = formatter.report_to_text(report)
            file_path = file_writer.save_report_txt(
                report_text,
                topic="_".join(enhanced_prompt.topics[:2]),
            )
            logger.info(f"Report saved to: {file_path}")

            # Prepare response
            pipeline_time = time.time() - pipeline_start
            logger.info("=" * 80)
            logger.info(f"Pipeline completed in {pipeline_time:.1f}s")
            logger.info("=" * 80)

            response = FullResearchResponse(
                report=report,
                file_path=str(file_path),
                status="completed",
                total_execution_time_seconds=pipeline_time,
            )

            return response

        except Exception as e:
            pipeline_time = time.time() - pipeline_start
            logger.error(f"Pipeline failed after {pipeline_time:.1f}s: {str(e)}")
            logger.exception("Full traceback:")
            raise


# Singleton instance
_orchestrator = None


def get_orchestrator() -> ResearchOrchestrator:
    """Get orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ResearchOrchestrator()
        logger.info("Research orchestrator initialized")
    return _orchestrator
