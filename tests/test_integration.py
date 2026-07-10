"""Integration tests for the research pipeline."""

import pytest

from app.services.orchestration import ResearchOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_initialization():
    """Test orchestrator can be created."""
    orchestrator = ResearchOrchestrator()
    assert orchestrator is not None


@pytest.mark.asyncio
async def test_full_pipeline_structure(
    mock_llm_service,
    mock_search_client,
):
    """Test the overall pipeline structure."""
    # This is a structural test - verifies all pieces can be imported
    from app.agents.formatter import get_formatter
    from app.agents.planner import get_planner
    from app.agents.prompt_enhancer import get_prompt_clarifier
    from app.agents.worker import get_worker
    from app.services.orchestration import get_orchestrator

    assert get_prompt_clarifier() is not None
    assert get_planner() is not None
    assert get_worker() is not None
    assert get_formatter() is not None
    assert get_orchestrator() is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
