"""Unit tests for agents."""

import pytest
from unittest.mock import patch
from app.agents.prompt_enhancer import PromptClarifierAgent
from app.agents.planner import PlannerAgent
from app.agents.worker import WorkerAgent
from app.agents.formatter import FormatterAgent
from app.models.schemas import EnhancedPrompt
from tests.fixtures import (
    mock_enhanced_prompt,
    mock_research_tasks,
    mock_task_results,
    mock_research_report,
    mock_llm_service,
    mock_search_client,
)


@pytest.mark.asyncio
async def test_prompt_clarifier_enhance_prompt(mock_llm_service):
    """Test prompt clarification."""
    with patch(
        "app.agents.prompt_enhancer.get_llm_service",
        return_value=mock_llm_service,
    ):
        agent = PromptClarifierAgent()
        result = await agent.enhance_prompt("Research AI and blockchain")

        assert isinstance(result, EnhancedPrompt)
        assert len(result.topics) > 0
        assert result.research_depth in ["quick", "medium", "deep"]


@pytest.mark.asyncio
async def test_planner_create_plan(mock_llm_service, mock_enhanced_prompt):
    """Test research plan creation."""
    with patch(
        "app.agents.planner.get_llm_service",
        return_value=mock_llm_service,
    ):
        agent = PlannerAgent()
        tasks = await agent.create_plan(mock_enhanced_prompt)

        assert len(tasks) > 0
        assert all(hasattr(t, "task_id") for t in tasks)
        assert all(hasattr(t, "search_query") for t in tasks)


@pytest.mark.asyncio
async def test_worker_execute_task(mock_llm_service, mock_search_client):
    """Test single task execution."""
    with patch(
        "app.agents.worker.get_llm_service",
        return_value=mock_llm_service,
    ), patch(
        "app.agents.worker.get_search_client",
        return_value=mock_search_client,
    ):
        from app.models.schemas import ResearchTask

        task = ResearchTask(
            task_id=1,
            topic="Test Topic",
            subtopic="overview",
            search_query="test query",
            description="Test task",
        )

        agent = WorkerAgent()
        result = await agent.execute_task(task)

        assert result.task_id == 1
        assert result.status in ["completed", "failed", "partial"]


@pytest.mark.asyncio
async def test_formatter_format_report(
    mock_llm_service,
    mock_task_results,
    mock_enhanced_prompt,
):
    """Test report formatting."""
    with patch(
        "app.agents.formatter.get_llm_service",
        return_value=mock_llm_service,
    ):
        agent = FormatterAgent()
        report = await agent.format_report(mock_task_results, mock_enhanced_prompt)

        assert report.title
        assert len(report.sections) > 0
        assert report.total_words > 0


@pytest.mark.asyncio
async def test_formatter_report_to_text(mock_research_report):
    """Test report text conversion."""
    agent = FormatterAgent()
    text = agent.report_to_text(mock_research_report)

    assert "Research Report" in text
    assert "Conclusion" in text
    assert "Sources" in text


def test_formatter_group_results_by_topic(mock_task_results):
    """Test grouping results by topic."""
    agent = FormatterAgent()
    grouped = agent._group_results_by_topic(mock_task_results)

    assert "Quantum Computing" in grouped
    assert len(grouped["Quantum Computing"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
