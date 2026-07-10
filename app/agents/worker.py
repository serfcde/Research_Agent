"""Worker Agent - Execute research tasks concurrently."""

import asyncio
import time

from app.models.schemas import ResearchSource, ResearchTask, TaskResult
from app.services.llm_service import get_llm_service
from app.tools.web_search import get_search_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WorkerAgent:
    """Agent for executing research tasks."""

    def __init__(self):
        """Initialize worker agent."""
        self.llm = get_llm_service()
        self.search_client = get_search_client()
        self.max_concurrent = 2
        self.task_timeout = 30

    async def execute_task(self, task: ResearchTask) -> TaskResult:
        """
        Execute a single research task.

        Args:
            task: Research task to execute

        Returns:
            Task result with findings
        """
        start_time = time.time()
        logger.info(f"Executing task {task.task_id}: {task.description}")

        try:
            # Search the web
            logger.debug(f"Searching: {task.search_query}")
            content, sources = await asyncio.wait_for(
                self.search_client.search(task.search_query),
                timeout=self.task_timeout,
            )

            if not content or not content.strip():
                logger.warning(f"Task {task.task_id}: No content found")
                return TaskResult(
                    task_id=task.task_id,
                    topic=task.topic,
                    subtopic=task.subtopic,
                    status="partial",
                    findings="No content found for this search.",
                    sources=[],
                    execution_time_seconds=time.time() - start_time,
                    error_message="No search results returned",
                )

            # Summarize findings. If the LLM is rate-limited, keep the retrieved
            # search content and sources instead of losing the research result.
            logger.debug(f"Task {task.task_id}: Summarizing {len(content)} chars...")
            try:
                findings = await self.llm.summarize_content(content, max_words=300)
                status = "completed"
                error_message = None
            except Exception as summarization_error:
                logger.warning(
                    f"Task {task.task_id}: Summarization failed, using source snippets: {str(summarization_error)}"
                )
                findings = self._fallback_findings(content, sources)
                status = "partial"
                error_message = f"Summarization failed: {str(summarization_error)}"

            execution_time = time.time() - start_time
            logger.info(f"Task {task.task_id} completed in {execution_time:.1f}s with status={status}")

            return TaskResult(
                task_id=task.task_id,
                topic=task.topic,
                subtopic=task.subtopic,
                status=status,
                findings=findings,
                sources=sources,
                execution_time_seconds=execution_time,
                error_message=error_message,
            )

        except TimeoutError:
            logger.error(f"Task {task.task_id} timed out after {self.task_timeout}s")
            return TaskResult(
                task_id=task.task_id,
                topic=task.topic,
                subtopic=task.subtopic,
                status="failed",
                findings="Task timed out",
                sources=[],
                execution_time_seconds=time.time() - start_time,
                error_message="Task exceeded timeout limit",
            )

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {str(e)}")
            return TaskResult(
                task_id=task.task_id,
                topic=task.topic,
                subtopic=task.subtopic,
                status="failed",
                findings="Task execution failed",
                sources=[],
                execution_time_seconds=time.time() - start_time,
                error_message=str(e),
            )

    def _fallback_findings(self, content: str, sources: list[ResearchSource]) -> str:
        """Create readable findings from search snippets when LLM summarization fails."""
        snippets = []
        for source in sources[:5]:
            if source.snippet:
                snippets.append(f"{source.title}: {source.snippet}")

        fallback = " ".join(snippets) if snippets else content
        return fallback[:1200] if fallback else "Search returned sources, but no snippet content was available."

    async def execute_tasks(self, tasks: list[ResearchTask]) -> list[TaskResult]:
        """
        Execute multiple research tasks concurrently.

        Args:
            tasks: List of research tasks

        Returns:
            List of task results
        """
        logger.info(f"Executing {len(tasks)} tasks with max concurrency {self.max_concurrent}")

        # Split into batches for concurrent execution
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def execute_with_semaphore(task: ResearchTask) -> TaskResult:
            async with semaphore:
                return await self.execute_task(task)

        # Execute all tasks concurrently
        results = await asyncio.gather(
            *[execute_with_semaphore(task) for task in tasks],
            return_exceptions=False,
        )

        # Log summary
        completed = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "failed")
        partial = sum(1 for r in results if r.status == "partial")

        logger.info(f"Task execution summary: {completed} completed, {partial} partial, {failed} failed")

        return results


# Singleton instance
_worker_agent = None


def get_worker() -> WorkerAgent:
    """Get worker agent singleton."""
    global _worker_agent
    if _worker_agent is None:
        _worker_agent = WorkerAgent()
        logger.info("Worker agent initialized")
    return _worker_agent
