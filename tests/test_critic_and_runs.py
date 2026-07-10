"""Tests for the critic replan loop, planner gap mode, run store, auth and API hardening."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agents.critic import CriticAgent, VERDICT_NEEDS_MORE, VERDICT_SUFFICIENT
from app.agents.planner import PlannerAgent
from app.config.settings import settings
from app.graph.nodes import critic_node, route_after_critic
from app.models.schemas import EnhancedPrompt, ResearchTask, TaskResult
from app.services.run_store import InMemoryRunStore


def make_enhanced() -> EnhancedPrompt:
    return EnhancedPrompt(
        topics=["Topic A"],
        research_depth="medium",
        required_sections=["Overview"],
        compare_topics=False,
        focus_areas=[],
    )


def make_result(task_id=1, status="completed") -> TaskResult:
    return TaskResult(
        task_id=task_id, topic="Topic A", subtopic="overview", status=status,
        findings="Findings text", sources=[], execution_time_seconds=1.0,
    )


# --------------------------------------------------------------------------- #
# Critic + routing                                                             #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestCriticLoop:
    async def test_route_replans_on_gaps(self):
        state = {"verdict": VERDICT_NEEDS_MORE, "gaps": ["missing subtopic"]}
        assert route_after_critic(state) == "planner"

    async def test_route_formats_when_sufficient(self):
        assert route_after_critic({"verdict": VERDICT_SUFFICIENT, "gaps": []}) == "formatter"

    async def test_route_formats_when_needs_more_but_no_gaps(self):
        assert route_after_critic({"verdict": VERDICT_NEEDS_MORE, "gaps": []}) == "formatter"

    async def test_critic_node_caps_iterations(self):
        """Even when the judge wants more research, the cap forces formatting."""
        evaluation = {"coverage_score": 0.4, "gaps": ["gap 1"], "verdict": VERDICT_NEEDS_MORE}
        mock_critic = AsyncMock()
        mock_critic.evaluate = AsyncMock(return_value=evaluation)

        state = {
            "enhanced_prompt": make_enhanced(),
            "task_results": [make_result()],
            "iteration": 1,          # this critic pass becomes iteration 2
            "max_iterations": 2,
        }
        with patch("app.graph.nodes.get_critic", return_value=mock_critic):
            update = await critic_node(state, {"configurable": {}})

        assert update["verdict"] == VERDICT_SUFFICIENT
        assert update["gaps"] == []
        assert update["iteration"] == 2
        assert route_after_critic({**state, **update}) == "formatter"

    async def test_critic_node_requests_replan_below_cap(self):
        evaluation = {"coverage_score": 0.4, "gaps": ["gap 1"], "verdict": VERDICT_NEEDS_MORE}
        mock_critic = AsyncMock()
        mock_critic.evaluate = AsyncMock(return_value=evaluation)

        state = {
            "enhanced_prompt": make_enhanced(),
            "task_results": [make_result()],
            "iteration": 0,
            "max_iterations": 2,
        }
        with patch("app.graph.nodes.get_critic", return_value=mock_critic):
            update = await critic_node(state, {"configurable": {}})

        assert update["verdict"] == VERDICT_NEEDS_MORE
        assert update["gaps"] == ["gap 1"]
        assert route_after_critic({**state, **update}) == "planner"

    async def test_critic_agent_never_loops_on_judge_failure(self):
        mock_llm = AsyncMock()
        mock_llm.call_llm_json = AsyncMock(side_effect=RuntimeError("judge down"))
        with patch("app.agents.critic.get_llm_service", return_value=mock_llm):
            critic = CriticAgent()
        result = await critic.evaluate(make_enhanced(), [make_result()])
        assert result["verdict"] == VERDICT_SUFFICIENT

    async def test_critic_agent_drops_verdict_without_gaps(self):
        mock_llm = AsyncMock()
        mock_llm.call_llm_json = AsyncMock(
            return_value={"coverage_score": 0.3, "gaps": [], "verdict": "needs_more"}
        )
        with patch("app.agents.critic.get_llm_service", return_value=mock_llm):
            critic = CriticAgent()
        result = await critic.evaluate(make_enhanced(), [make_result()])
        assert result["verdict"] == VERDICT_SUFFICIENT


# --------------------------------------------------------------------------- #
# Planner gap mode                                                             #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestPlannerGapMode:
    async def test_gap_plan_produces_incremental_tasks(self):
        gap_tasks = [
            {"topic": "Topic A", "subtopic": "hardware", "search_query": "topic a hardware limits", "description": "d"},
        ]
        mock_llm = AsyncMock()
        mock_llm.call_llm = AsyncMock(return_value=json.dumps(gap_tasks))
        with patch("app.agents.planner.get_llm_service", return_value=mock_llm):
            planner = PlannerAgent()

        existing = [
            ResearchTask(task_id=7, topic="Topic A", subtopic="overview",
                         search_query="topic a overview", description="d"),
        ]
        tasks = await planner.create_plan(make_enhanced(), gaps=["hardware limits"], existing_tasks=existing)

        assert len(tasks) == 1
        assert tasks[0].task_id == 8  # continues numbering
        assert tasks[0].search_query == "topic a hardware limits"

    async def test_gap_plan_skips_duplicate_queries(self):
        gap_tasks = [
            {"subtopic": "overview", "search_query": "topic a overview", "description": "duplicate"},
        ]
        mock_llm = AsyncMock()
        mock_llm.call_llm = AsyncMock(return_value=json.dumps(gap_tasks))
        with patch("app.agents.planner.get_llm_service", return_value=mock_llm):
            planner = PlannerAgent()

        existing = [
            ResearchTask(task_id=1, topic="Topic A", subtopic="overview",
                         search_query="topic a overview", description="d"),
        ]
        tasks = await planner.create_plan(make_enhanced(), gaps=["overview again"], existing_tasks=existing)
        assert tasks == []

    async def test_gap_plan_falls_back_when_llm_fails(self):
        mock_llm = AsyncMock()
        mock_llm.call_llm = AsyncMock(side_effect=RuntimeError("down"))
        with patch("app.agents.planner.get_llm_service", return_value=mock_llm):
            planner = PlannerAgent()

        tasks = await planner.create_plan(make_enhanced(), gaps=["hardware limits"], existing_tasks=[])
        assert len(tasks) == 1
        assert "hardware limits" in tasks[0].search_query


# --------------------------------------------------------------------------- #
# Run store                                                                    #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestInMemoryRunStore:
    async def test_lifecycle(self):
        store = InMemoryRunStore()
        await store.create_run("r1", "prompt")
        run = await store.get_run("r1")
        assert run["status"] == "running"

        await store.mark_completed("r1", {"report": {"title": "t"}})
        run = await store.get_run("r1")
        assert run["status"] == "completed"
        assert run["report"]["report"]["title"] == "t"

        await store.mark_failed("r1", "boom")  # idempotent-ish update
        assert (await store.get_run("r1"))["status"] == "failed"

    async def test_list_runs_excludes_reports_and_sorts_newest_first(self):
        store = InMemoryRunStore()
        await store.create_run("r1", "first")
        await asyncio.sleep(0.01)
        await store.create_run("r2", "second")
        runs = await store.list_runs()
        assert [r["id"] for r in runs] == ["r2", "r1"]
        assert all("report" not in r for r in runs)

    async def test_missing_run_is_none(self):
        assert await InMemoryRunStore().get_run("nope") is None


# --------------------------------------------------------------------------- #
# API hardening                                                                #
# --------------------------------------------------------------------------- #

class TestApiKeyAuth:
    def test_rejected_without_key_when_configured(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(settings, "api_keys", "secret-1,secret-2")
        response = client.get("/api/runs")
        assert response.status_code == 401

    def test_accepted_with_valid_key(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(settings, "api_keys", "secret-1,secret-2")
        response = client.get("/api/runs", headers={"X-API-Key": "secret-2"})
        assert response.status_code == 200

    def test_status_stays_public(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(settings, "api_keys", "secret-1")
        assert client.get("/api/status").status_code == 200

    def test_auth_disabled_when_unset(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(settings, "api_keys", "")
        assert client.get("/api/runs").status_code == 200


class TestRequestValidation:
    def test_empty_prompt_rejected(self, client: TestClient):
        response = client.post("/api/research", json={"prompt": "   "})
        assert response.status_code == 422

    def test_oversized_prompt_rejected(self, client: TestClient):
        response = client.post("/api/research", json={"prompt": "x" * 3000})
        assert response.status_code == 422


class TestBackgroundRunFlow:
    def test_research_202_then_completes_and_streams(self, client: TestClient):
        """202 → background pipeline (mocked LLM/search) → completed run → SSE replay."""
        response = client.post(
            "/api/research",
            json={"prompt": "Research testing topics"},
            headers={"X-Trace-Id": f"test-run-{time.time()}"},
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        for _ in range(100):
            run = client.get(f"/api/research/{run_id}").json()
            if run["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)
        assert run["status"] == "completed"
        assert run["report"]["report"]["title"]

        runs = client.get("/api/runs").json()["runs"]
        assert any(r["id"] == run_id for r in runs)

        # SSE replay of a finished run ends with run_end
        events = []
        with client.stream("GET", f"/api/research/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                if events and events[-1].get("event_type") == "run_end":
                    break
        node_events = [e["node"] for e in events if e["event_type"] == "node_start"]
        assert "prompt_enhancer" in node_events
        assert "critic" in node_events
        assert events[-1]["event_type"] == "run_end"

    def test_duplicate_run_id_conflicts(self, client: TestClient):
        headers = {"X-Trace-Id": f"dup-run-{time.time()}"}
        first = client.post("/api/research", json={"prompt": "Research one"}, headers=headers)
        assert first.status_code == 202
        second = client.post("/api/research", json={"prompt": "Research two"}, headers=headers)
        assert second.status_code == 409

    def test_unknown_run_404s(self, client: TestClient):
        assert client.get("/api/research/does-not-exist").status_code == 404
        assert client.get("/api/research/does-not-exist/events").status_code == 404
