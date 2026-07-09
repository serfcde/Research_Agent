"""Tests for planner agent (LLM mocked — no live API calls)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.planner import PlannerAgent
from app.models.schemas import EnhancedPrompt, ResearchTask


def _make_planner(llm_response: str) -> PlannerAgent:
    """Create a PlannerAgent whose LLM returns a fixed response."""
    mock_llm = AsyncMock()
    mock_llm.call_llm = AsyncMock(return_value=llm_response)
    with patch("app.agents.planner.get_llm_service", return_value=mock_llm):
        return PlannerAgent()


@pytest.mark.asyncio
class TestPlannerAgent:
    """Test planner agent."""

    async def test_create_plan_single_topic_quick(self):
        """Test creating quick plan for single topic."""
        planner = _make_planner(
            json.dumps(
                [
                    {
                        "subtopic": "overview",
                        "search_query": "quantum computing overview 2026",
                        "description": "Get overview of quantum computing",
                    }
                ]
            )
        )
        enhanced = EnhancedPrompt(
            topics=["Quantum Computing"],
            research_depth="quick",
            required_sections=["Overview"],
            compare_topics=False,
            focus_areas=[],
        )

        tasks = await planner.create_plan(enhanced)

        assert len(tasks) > 0
        assert all(isinstance(t, ResearchTask) for t in tasks)
        assert all(t.topic == "Quantum Computing" for t in tasks)

    async def test_create_plan_multi_topic_medium(self):
        """Test creating medium plan for multiple topics."""
        planner = _make_planner(
            json.dumps(
                [
                    {
                        "topic": "AI",
                        "subtopic": "overview",
                        "search_query": "AI overview 2026",
                        "description": "Get overview of AI",
                    },
                    {
                        "topic": "AI",
                        "subtopic": "applications",
                        "search_query": "AI applications 2026",
                        "description": "Research AI applications",
                    },
                    {
                        "topic": "Machine Learning",
                        "subtopic": "overview",
                        "search_query": "machine learning overview 2026",
                        "description": "Get overview of machine learning",
                    },
                ]
            )
        )
        enhanced = EnhancedPrompt(
            topics=["AI", "Machine Learning"],
            research_depth="medium",
            required_sections=["Overview", "Applications"],
            compare_topics=True,
            focus_areas=["Industry Impact"],
        )

        tasks = await planner.create_plan(enhanced)

        assert len(tasks) >= 2
        topics_in_tasks = set(t.topic for t in tasks)
        assert len(topics_in_tasks) >= 2

    async def test_create_plan_falls_back_on_invalid_llm_output(self):
        """Unparseable LLM output falls back to default tasks."""
        planner = _make_planner("I cannot produce JSON right now, sorry!")
        enhanced = EnhancedPrompt(
            topics=["Blockchain"],
            research_depth="medium",
            required_sections=["Overview", "Applications", "Challenges"],
            compare_topics=False,
            focus_areas=[],
        )

        tasks = await planner.create_plan(enhanced)

        assert len(tasks) > 0
        assert all(t.topic == "Blockchain" for t in tasks)

    async def test_create_default_tasks(self):
        """Test default task creation fallback."""
        planner = _make_planner("unused")
        enhanced = EnhancedPrompt(
            topics=["Blockchain"],
            research_depth="medium",
            required_sections=["Overview", "Applications", "Challenges"],
            compare_topics=False,
            focus_areas=[],
        )

        tasks = planner._create_default_tasks(enhanced)

        assert len(tasks) > 0
        assert all(isinstance(t, ResearchTask) for t in tasks)
        # Should have at least overview, applications, challenges
        subtopics = set(t.subtopic for t in tasks)
        assert "overview" in subtopics

    async def test_plan_tasks_have_search_queries(self):
        """Test that all created tasks have search queries."""
        planner = _make_planner(
            json.dumps(
                [
                    {
                        "subtopic": "overview",
                        "search_query": "neural networks overview 2026",
                        "description": "Get overview of neural networks",
                    }
                ]
            )
        )
        enhanced = EnhancedPrompt(
            topics=["Neural Networks"],
            research_depth="quick",
            required_sections=["Overview"],
            compare_topics=False,
            focus_areas=[],
        )

        tasks = await planner.create_plan(enhanced)

        for task in tasks:
            assert task.search_query
            assert len(task.search_query) > 0
            assert len(task.description) > 0
