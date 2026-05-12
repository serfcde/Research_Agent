"""Pytest configuration and fixtures."""

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create test app instance."""
    app = create_app()
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


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
