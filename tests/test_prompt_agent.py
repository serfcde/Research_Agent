"""Tests for prompt clarifier agent."""

import pytest
from app.agents.prompt_enhancer import get_prompt_clarifier


@pytest.mark.asyncio
class TestPromptClarifierAgent:
    """Test prompt clarifier agent."""

    async def test_enhance_single_topic_prompt(self):
        """Test enhancing a single topic prompt."""
        clarifier = get_prompt_clarifier()
        result = await clarifier.enhance_prompt("What is artificial intelligence?")
        
        assert result is not None
        assert len(result.topics) > 0
        assert result.research_depth in ["quick", "medium", "deep"]
        assert len(result.required_sections) > 0

    async def test_enhance_multi_topic_prompt(self):
        """Test enhancing a multi-topic prompt."""
        clarifier = get_prompt_clarifier()
        result = await clarifier.enhance_prompt(
            "Compare quantum computing vs classical computing"
        )
        
        assert len(result.topics) >= 2
        assert result.compare_topics is True

    async def test_enhance_prompt_with_depth_hints(self):
        """Test enhancing prompt with depth hints."""
        clarifier = get_prompt_clarifier()
        result = await clarifier.enhance_prompt(
            "Deep research on blockchain technology"
        )
        
        assert len(result.topics) > 0
        assert result.research_depth in ["quick", "medium", "deep"]

    async def test_extract_topics_heuristically(self):
        """Test heuristic topic extraction."""
        clarifier = get_prompt_clarifier()
        
        topics = clarifier._extract_topics_heuristically(
            "Research AI and machine learning"
        )
        
        assert len(topics) > 0
        assert any("AI" in t or "machine learning" in t for t in topics)

    async def test_normalize_topics(self):
        """Test topic normalization."""
        clarifier = get_prompt_clarifier()
        
        topics = clarifier._normalize_topics(
            ["analyze artificial intelligence", "blockchain"],
            "Research AI and blockchain"
        )
        
        assert len(topics) > 0
        # Should not have action verbs
        assert not any(verb in topics[0].lower() for verb in ["analyze", "research"])
