"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schemas import ResearchSource

# Expose shared fixtures (mock_llm_service, mock_task_results, ...)
pytest_plugins = ["tests.fixtures"]


@pytest.fixture(autouse=True)
def no_live_apis(monkeypatch):
    """
    Keep the suite hermetic: block real LLM calls and can search results
    at class level, so it also covers module-level agent singletons.

    Agents handle LLM failure via their heuristic fallback paths, which is
    exactly what these tests should exercise. Tests that want specific LLM
    output inject their own mock service instead (see tests/fixtures.py).
    """
    from app.services.llm_service import LLMService
    from app.tools.web_search import WebSearchClient

    async def _blocked_llm(self, *args, **kwargs):
        raise RuntimeError("Live LLM calls are disabled in tests")

    async def _canned_search(self, query, use_fallback=True):
        return (
            f"Canned search results for: {query}",
            [
                ResearchSource(
                    title="Test Source",
                    url="https://example.com/test",
                    snippet="Canned snippet for tests",
                )
            ],
        )

    monkeypatch.setattr(LLMService, "call_llm", _blocked_llm)
    monkeypatch.setattr(WebSearchClient, "search", _canned_search)


@pytest.fixture
def app():
    """Create test app instance."""
    app = create_app()
    return app


@pytest.fixture
def client(app, monkeypatch):
    """
    Test client with a running lifespan (persistent event loop), so
    background research tasks actually execute during the test. Dummy
    keys satisfy the startup fail-fast; no live call can happen anyway
    thanks to the autouse no_live_apis fixture.
    """
    from app.config.settings import settings

    monkeypatch.setattr(settings, "groq_api_key", settings.groq_api_key or "test-key")
    monkeypatch.setattr(settings, "tavily_api_key", settings.tavily_api_key or "test-key")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_prompt():
    """Sample user prompt for testing."""
    return "Research quantum computing and artificial intelligence"


@pytest.fixture
def sample_enhanced_prompt():
    """Sample enhanced prompt for testing."""
    return {
        "topics": ["Quantum Computing", "Artificial Intelligence"],
        "research_depth": "medium",
        "required_sections": ["Overview", "Applications", "Challenges", "Future Trends"],
        "compare_topics": True,
        "focus_areas": ["Industry Impact", "Technical Challenges"],
    }


@pytest.fixture
def sample_research_task():
    """Sample research task for testing."""
    return {
        "task_id": 1,
        "topic": "Quantum Computing",
        "subtopic": "overview",
        "search_query": "quantum computing overview 2026",
        "description": "Get overview of quantum computing",
    }
