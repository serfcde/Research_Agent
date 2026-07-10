"""Tests for Prometheus metrics exposure."""

from fastapi.testclient import TestClient

from app.utils import metrics


class TestMetricsEndpoint:
    def test_metrics_endpoint_exposes_pipeline_metrics(self, client: TestClient):
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        for name in (
            "research_runs_started_total",
            "research_runs_finished_total",
            "research_run_duration_seconds",
            "research_node_duration_seconds",
            "research_llm_tokens_total",
            "research_llm_cost_usd_total",
            "research_active_runs",
            "research_sse_subscribers",
        ):
            assert name in body, f"missing metric: {name}"


class TestMetricRecording:
    def test_run_lifecycle_updates_counters(self):
        started_before = metrics.RUNS_STARTED._value.get()
        completed_before = metrics.RUNS_FINISHED.labels(status="completed")._value.get()
        cost_before = metrics.LLM_COST_USD._value.get()
        active_before = metrics.ACTIVE_RUNS._value.get()

        metrics.record_run_start()
        assert metrics.ACTIVE_RUNS._value.get() == active_before + 1

        metrics.record_node_end("worker", 1500.0, error=False, output={})
        metrics.record_node_end("critic", 300.0, error=False, output={"verdict": "needs_more"})
        metrics.record_run_end(
            12.5, "completed",
            {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        )

        assert metrics.RUNS_STARTED._value.get() == started_before + 1
        assert metrics.RUNS_FINISHED.labels(status="completed")._value.get() == completed_before + 1
        assert metrics.ACTIVE_RUNS._value.get() == active_before
        # 1M prompt tokens * 0.59 + 1M completion * 0.79
        assert round(metrics.LLM_COST_USD._value.get() - cost_before, 2) == 1.38

    def test_replans_counted_only_on_needs_more(self):
        before = metrics.REPLANS._value.get()
        metrics.record_node_end("critic", 100.0, error=False, output={"verdict": "sufficient"})
        assert metrics.REPLANS._value.get() == before
        metrics.record_node_end("critic", 100.0, error=False, output={"verdict": "needs_more"})
        assert metrics.REPLANS._value.get() == before + 1
