"""
Evaluation harness for the research pipeline.

Runs the full pipeline over a fixed prompt dataset and scores every
report on grounding, coverage and structure, plus operational metrics
(latency per node, tokens, cost, replan/fallback rates) pulled from the
tracker trace.

Usage:
    python -m evals.run_evals                  # full dataset
    python -m evals.run_evals --limit 3        # first N prompts
    python -m evals.run_evals --compare        # fail (exit 1) on regression vs baseline
    python -m evals.run_evals --save-baseline  # promote this run to baseline

Requires GROQ_API_KEY and TAVILY_API_KEY (runs the real pipeline).
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.graph.tracker import read_run_events
from app.services.orchestration import get_orchestrator
from evals.judges import check_structure, judge_coverage, judge_grounding

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
BASELINE_PATH = Path(__file__).parent / "baseline.json"

# Groq llama-3.3-70b-versatile pricing (USD per million tokens).
COST_PER_M_INPUT = 0.59
COST_PER_M_OUTPUT = 0.79

# --compare fails when a mean quality score drops more than this
# relative fraction below the baseline.
REGRESSION_TOLERANCE = 0.10


def load_dataset(limit: int | None) -> list[dict]:
    items = []
    with DATASET_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items[:limit] if limit else items


def ops_metrics(run_id: str) -> dict:
    """Operational metrics derived from the tracker trace of one run."""
    events = read_run_events(run_id)
    node_ms: dict[str, float] = {}
    iterations = 0
    task_statuses: list[str] = []
    usage: dict = {}
    total_seconds = None

    for event in events:
        data = event.get("data", {})
        if event["event_type"] == "node_end":
            node_ms[event["node"]] = node_ms.get(event["node"], 0.0) + (data.get("duration_ms") or 0.0)
            output = data.get("output", {})
            if event["node"] == "critic":
                iterations = max(iterations, output.get("iteration", 0))
            if event["node"] == "worker":
                task_statuses.extend(r.get("status", "") for r in output.get("results", []))
        elif event["event_type"] == "run_end":
            usage = data.get("usage", {}) or {}
            total_seconds = data.get("total_seconds")

    cost = (
        usage.get("prompt_tokens", 0) / 1e6 * COST_PER_M_INPUT
        + usage.get("completion_tokens", 0) / 1e6 * COST_PER_M_OUTPUT
    )
    completed = sum(1 for s in task_statuses if s == "completed")
    return {
        "total_seconds": total_seconds,
        "node_ms": {k: round(v, 1) for k, v in node_ms.items()},
        "iterations": iterations,
        "tasks_total": len(task_statuses),
        "tasks_completed": completed,
        "fallback_rate": round(1 - completed / len(task_statuses), 3) if task_statuses else None,
        "tokens": usage,
        "cost_usd": round(cost, 5),
    }


async def evaluate_item(item: dict) -> dict:
    run_id = f"eval-{item['id']}-{int(time.time())}"
    started = time.time()

    orchestrator = get_orchestrator()
    response = await orchestrator.run_research_pipeline(item["prompt"], run_id=run_id)
    report = response.report

    grounding = await judge_grounding(report)
    coverage = await judge_coverage(item["prompt"], report)
    structure = check_structure(report, item.get("expected_topics", 1))

    return {
        "id": item["id"],
        "prompt": item["prompt"],
        "run_id": run_id,
        "grounding": grounding,
        "coverage": coverage,
        "structure": structure,
        "ops": ops_metrics(run_id),
        "wall_seconds": round(time.time() - started, 1),
        "report_words": report.total_words,
        "citations": len(report.citations),
    }


def aggregate(results: list[dict]) -> dict:
    def mean(values):
        values = [v for v in values if v is not None]
        return round(statistics.mean(values), 3) if values else None

    def pct(values, p):
        values = sorted(v for v in values if v is not None)
        if not values:
            return None
        idx = min(len(values) - 1, round(p / 100 * (len(values) - 1)))
        return round(values[idx], 1)

    latencies = [r["ops"]["total_seconds"] for r in results]
    return {
        "runs": len(results),
        "grounding_mean": mean([r["grounding"]["score"] for r in results]),
        "coverage_mean": mean([r["coverage"]["score"] for r in results]),
        "structure_mean": mean([r["structure"]["score"] for r in results]),
        "latency_p50_s": pct(latencies, 50),
        "latency_p95_s": pct(latencies, 95),
        "cost_mean_usd": mean([r["ops"]["cost_usd"] for r in results]),
        "replan_rate": mean([1.0 if r["ops"]["iterations"] > 1 else 0.0 for r in results]),
        "fallback_rate_mean": mean([r["ops"]["fallback_rate"] for r in results]),
    }


def print_summary(results: list[dict], summary: dict) -> None:
    print("\n| id | grounding | coverage | structure | latency (s) | cost ($) | iters |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        print(
            f"| {r['id']} | {r['grounding']['score']:.2f} | {r['coverage']['score']:.2f} "
            f"| {r['structure']['score']:.2f} | {r['ops']['total_seconds'] or '-'} "
            f"| {r['ops']['cost_usd']:.4f} | {r['ops']['iterations']} |"
        )
    print("\nAggregate:")
    for key, value in summary.items():
        print(f"  {key:20} {value}")


def compare_to_baseline(summary: dict) -> int:
    if not BASELINE_PATH.exists():
        print("\nNo baseline.json found — run with --save-baseline first.", file=sys.stderr)
        return 2

    baseline = json.loads(BASELINE_PATH.read_text())["summary"]
    failures = []
    for metric in ("grounding_mean", "coverage_mean", "structure_mean"):
        base, current = baseline.get(metric), summary.get(metric)
        if base and current is not None and current < base * (1 - REGRESSION_TOLERANCE):
            failures.append(f"{metric}: {current} < baseline {base} (-{REGRESSION_TOLERANCE:.0%} tolerance)")

    if failures:
        print("\nREGRESSION DETECTED:", file=sys.stderr)
        for failure in failures:
            print(f"  ✗ {failure}", file=sys.stderr)
        return 1

    print("\n✓ No regression vs baseline "
          f"(grounding {baseline.get('grounding_mean')} → {summary.get('grounding_mean')}, "
          f"coverage {baseline.get('coverage_mean')} → {summary.get('coverage_mean')})")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the research pipeline eval suite")
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N prompts")
    parser.add_argument("--compare", action="store_true", help="Exit 1 if quality regressed vs baseline")
    parser.add_argument("--save-baseline", action="store_true", help="Save this run as the new baseline")
    args = parser.parse_args()

    items = load_dataset(args.limit)
    print(f"Evaluating {len(items)} prompts...")

    results = []
    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {item['id']}: {item['prompt'][:60]}...")
        try:
            results.append(await evaluate_item(item))
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            results.append({
                "id": item["id"], "prompt": item["prompt"], "error": str(exc),
                "grounding": {"score": 0.0}, "coverage": {"score": 0.0},
                "structure": {"score": 0.0},
                "ops": {"total_seconds": None, "cost_usd": 0.0, "iterations": 0, "fallback_rate": None},
            })

    summary = aggregate(results)
    print_summary(results, summary)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {"timestamp": stamp, "summary": summary, "results": results}
    out_path = RESULTS_DIR / f"{stamp}.json"
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\nResults written to {out_path}")

    if args.save_baseline:
        BASELINE_PATH.write_text(json.dumps(payload, indent=2))
        print(f"Baseline saved to {BASELINE_PATH}")

    if args.compare:
        return compare_to_baseline(summary)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
