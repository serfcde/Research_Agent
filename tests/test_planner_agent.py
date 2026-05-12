"""Tests for planner agent."""

import pytest
from app.agents.planner import get_planner
from app.models.schemas import EnhancedPrompt, ResearchTask


@pytest.mark.asyncio
class TestPlannerAgent:
    """Test planner agent."""

    async def test_create_plan_single_topic_quick(self):
        """Test creating quick plan for single topic."""
        planner = get_planner()
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
        planner = get_planner()
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

    async def test_create_default_tasks(self):
        """Test default task creation fallback."""
        planner = get_planner()
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
        planner = get_planner()
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
