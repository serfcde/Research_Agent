"""Tests for the evaluation harness (LLM judges mocked)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models.schemas import ResearchReport, ResearchSource
from evals.judges import check_structure, extract_claims, judge_coverage, judge_grounding
from evals.run_evals import aggregate


def make_report(**overrides) -> ResearchReport:
    base = dict(
        title="Research Report: Topic A, Topic B",
        topics=["Topic A", "Topic B"],
        introduction=" ".join(["intro"] * 60),
        sections={
            "Topic A": " ".join(["Topic A has seen significant growth in recent years according to research."] * 12),
            "Topic B": " ".join(["Topic B adoption is accelerating across industries with measurable results."] * 12),
        },
        comparative_analysis="Both topics matter for different time horizons.",
        conclusion=" ".join(["conclusion"] * 40),
        citations=[
            ResearchSource(title=f"Source {i}", url=f"https://example.com/{i}", snippet=f"Snippet {i}")
            for i in range(5)
        ],
        total_words=1500,
    )
    base.update(overrides)
    return ResearchReport(**base)


class TestStructureChecks:
    def test_good_report_scores_high(self):
        result = check_structure(make_report(), expected_topics=2)
        assert result["score"] == 1.0
        assert all(result["checks"].values())

    def test_missing_citations_lowers_score(self):
        result = check_structure(make_report(citations=[]), expected_topics=2)
        assert result["score"] < 1.0
        assert result["checks"]["has_citations"] is False

    def test_missing_comparative_analysis_flagged_for_multi_topic(self):
        result = check_structure(make_report(comparative_analysis=""), expected_topics=2)
        assert result["checks"]["comparative_analysis_when_multi_topic"] is False

    def test_single_topic_does_not_require_comparison(self):
        report = make_report(comparative_analysis="", sections={"Topic A": " ".join(["content"] * 60)})
        result = check_structure(report, expected_topics=1)
        assert result["checks"]["comparative_analysis_when_multi_topic"] is True

    def test_word_count_bounds(self):
        result = check_structure(make_report(total_words=50), expected_topics=2)
        assert result["checks"]["word_count_sane"] is False


class TestExtractClaims:
    def test_extracts_substantive_sentences(self):
        claims = extract_claims(make_report())
        assert 0 < len(claims) <= 8
        assert all(len(c) >= 60 for c in claims)

    def test_empty_report_yields_no_claims(self):
        report = make_report(sections={"Topic A": "Short."})
        assert extract_claims(report) == []


@pytest.mark.asyncio
class TestGroundingJudge:
    async def test_all_supported_scores_one(self):
        mock_llm = AsyncMock()
        mock_llm.call_llm_json = AsyncMock(
            return_value={"verdicts": [{"claim": i, "verdict": "supported"} for i in range(1, 9)]}
        )
        with patch("evals.judges.get_llm_service", return_value=mock_llm):
            result = await judge_grounding(make_report())
        assert result["score"] == 1.0
        assert result["unsupported"] == 0

    async def test_mixed_verdicts_scores_fractionally(self):
        mock_llm = AsyncMock()
        mock_llm.call_llm_json = AsyncMock(
            return_value={
                "verdicts": [
                    {"claim": 1, "verdict": "supported"},
                    {"claim": 2, "verdict": "partial"},
                    {"claim": 3, "verdict": "unsupported"},
                    {"claim": 4, "verdict": "unsupported"},
                ]
            }
        )
        with patch("evals.judges.get_llm_service", return_value=mock_llm):
            result = await judge_grounding(make_report())
        # (1 + 0.5) / 4
        assert result["score"] == 0.375

    async def test_no_citations_scores_zero(self):
        result = await judge_grounding(make_report(citations=[]))
        assert result["score"] == 0.0
        assert result["claims_judged"] > 0


@pytest.mark.asyncio
class TestCoverageJudge:
    async def test_score_clamped_and_missing_capped(self):
        mock_llm = AsyncMock()
        mock_llm.call_llm_json = AsyncMock(
            return_value={"score": 1.7, "missing": [f"gap {i}" for i in range(10)]}
        )
        with patch("evals.judges.get_llm_service", return_value=mock_llm):
            result = await judge_coverage("Research things", make_report())
        assert result["score"] == 1.0
        assert len(result["missing"]) == 5


class TestAggregate:
    def test_aggregate_means_and_percentiles(self):
        results = [
            {
                "grounding": {"score": 0.8}, "coverage": {"score": 0.9}, "structure": {"score": 1.0},
                "ops": {"total_seconds": 10.0, "cost_usd": 0.01, "iterations": 1, "fallback_rate": 0.0},
            },
            {
                "grounding": {"score": 0.6}, "coverage": {"score": 0.7}, "structure": {"score": 0.8},
                "ops": {"total_seconds": 30.0, "cost_usd": 0.03, "iterations": 2, "fallback_rate": 0.5},
            },
        ]
        summary = aggregate(results)
        assert summary["runs"] == 2
        assert summary["grounding_mean"] == 0.7
        assert summary["coverage_mean"] == 0.8
        assert summary["latency_p50_s"] == 10.0
        assert summary["latency_p95_s"] == 30.0
        assert summary["replan_rate"] == 0.5
