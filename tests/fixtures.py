"""Test fixtures and utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.schemas import (
    EnhancedPrompt,
    ResearchTask,
    TaskResult,
    ResearchSource,
    ResearchReport,
)


@pytest.fixture
def mock_enhanced_prompt():
    """Create mock enhanced prompt."""
    return EnhancedPrompt(
        topics=["Quantum Computing", "Edge AI"],
        research_depth="medium",
        required_sections=["Overview", "Applications", "Challenges", "Future Trends"],
        compare_topics=True,
        focus_areas=["Industry adoption"],
    )


@pytest.fixture
def mock_research_tasks():
    """Create mock research tasks."""
    return [
        ResearchTask(
            task_id=1,
            topic="Quantum Computing",
            subtopic="overview",
            search_query="quantum computing overview 2026",
            description="Get overview of quantum computing",
        ),
        ResearchTask(
            task_id=2,
            topic="Quantum Computing",
            subtopic="applications",
            search_query="quantum computing applications 2026",
            description="Research quantum computing applications",
        ),
        ResearchTask(
            task_id=3,
            topic="Edge AI",
            subtopic="overview",
            search_query="edge AI overview 2026",
            description="Get overview of edge AI",
        ),
    ]


@pytest.fixture
def mock_task_results():
    """Create mock task results."""
    return [
        TaskResult(
            task_id=1,
            topic="Quantum Computing",
            subtopic="overview",
            status="completed",
            findings="Quantum computing is a revolutionary technology that uses quantum mechanics...",
            sources=[
                ResearchSource(
                    title="Quantum Computing Basics",
                    url="https://example.com/quantum",
                    snippet="Quantum computers process information...",
                ),
            ],
            execution_time_seconds=5.2,
        ),
        TaskResult(
            task_id=2,
            topic="Quantum Computing",
            subtopic="applications",
            status="completed",
            findings="Applications include cryptography, drug discovery, optimization...",
            sources=[
                ResearchSource(
                    title="Quantum Applications",
                    url="https://example.com/app",
                    snippet="Real-world quantum applications...",
                ),
            ],
            execution_time_seconds=4.8,
        ),
    ]


@pytest.fixture
def mock_research_report():
    """Create mock research report."""
    return ResearchReport(
        title="Research Report: Quantum Computing and Edge AI",
        topics=["Quantum Computing", "Edge AI"],
        introduction="This report explores quantum computing and edge AI...",
        sections={
            "Quantum Computing": "### Quantum Computing\n\nQuantum computing is...",
            "Edge AI": "### Edge AI\n\nEdge AI brings...",
        },
        comparative_analysis="Both technologies are transformative...",
        conclusion="In conclusion, both quantum computing and edge AI are important...",
        citations=[
            ResearchSource(
                title="Example Research Source",
                url="https://example.com/research",
                snippet="Example citation snippet",
            )
        ],
        total_words=2500,
    )


@pytest.fixture
def mock_llm_service():
    """Create mock LLM service."""
    service = AsyncMock()
    service.call_llm = AsyncMock(
        return_value='{"topics": ["Test Topic"], "research_depth": "medium"}'
    )
    service.call_llm_json = AsyncMock(
        return_value={"topics": ["Test Topic"], "research_depth": "medium"}
    )
    service.summarize_content = AsyncMock(
        return_value="This is a summary of the content..."
    )
    return service


@pytest.fixture
def mock_search_client():
    """Create mock search client."""
    client = AsyncMock()
    client.search = AsyncMock(
        return_value=(
            "Relevant research findings about the topic...",
            [
                ResearchSource(
                    title="Example Source",
                    url="https://example.com",
                    snippet="Example snippet",
                )
            ],
        )
    )
    return client


@pytest.fixture
def mock_file_writer():
    """Create mock file writer."""
    writer = MagicMock()
    writer.save_report_txt = MagicMock(
        return_value="/research_outputs/research_test_20260511_120000.txt"
    )
    return writer
