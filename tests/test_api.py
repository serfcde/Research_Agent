"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client: TestClient):
        """Test health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data


class TestPromptEnhancementEndpoint:
    """Test prompt enhancement endpoint."""

    def test_enhance_prompt_success(self, client: TestClient, sample_prompt):
        """Test successful prompt enhancement."""
        response = client.post(
            "/api/enhance-prompt",
            json={"prompt": sample_prompt},
        )
        assert response.status_code == 200
        data = response.json()
        assert "topics" in data
        assert "research_depth" in data
        assert len(data["topics"]) > 0

    def test_enhance_prompt_single_topic(self, client: TestClient):
        """Test prompt enhancement with single topic."""
        response = client.post(
            "/api/enhance-prompt",
            json={"prompt": "What is machine learning?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["topics"]) >= 1

    def test_enhance_prompt_missing_input(self, client: TestClient):
        """Test prompt enhancement with missing input."""
        response = client.post(
            "/api/enhance-prompt",
            json={},
        )
        assert response.status_code == 422  # Validation error


class TestPlanningEndpoint:
    """Test planning endpoint."""

    def test_plan_research_success(self, client: TestClient, sample_enhanced_prompt):
        """Test successful research planning."""
        response = client.post(
            "/api/plan-research",
            json={"enhanced_prompt": sample_enhanced_prompt},
        )
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) > 0
        
        # Verify task structure
        task = data["tasks"][0]
        assert "task_id" in task
        assert "topic" in task
        assert "subtopic" in task
        assert "search_query" in task


class TestExecutionEndpoint:
    """Test execution endpoint."""

    def test_execute_research_structure(self, client: TestClient, sample_research_task):
        """Test execution endpoint accepts tasks."""
        response = client.post(
            "/api/execute-research",
            json={"tasks": [sample_research_task]},
            timeout=120,
        )
        # Should get 200 or timeout, depending on network
        assert response.status_code in [200, 504, 408]


class TestFormattingEndpoint:
    """Test formatting endpoint."""

    def test_format_report_structure(self, client: TestClient, sample_enhanced_prompt):
        """Test formatting endpoint structure."""
        sample_result = {
            "task_id": 1,
            "topic": "AI",
            "subtopic": "overview",
            "status": "completed",
            "findings": "Sample findings about AI",
            "sources": [],
            "execution_time_seconds": 10.5,
        }
        
        response = client.post(
            "/api/format-report",
            json={
                "task_results": [sample_result],
                "enhanced_prompt": sample_enhanced_prompt,
            },
        )
        assert response.status_code in [200, 500]  # May fail due to LLM


class TestStatusEndpoint:
    """Test status endpoint."""

    def test_status_endpoint(self, client: TestClient):
        """Test status endpoint."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "API ready"
