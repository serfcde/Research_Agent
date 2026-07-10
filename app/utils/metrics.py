"""
Prometheus metrics for the research pipeline.

All metrics are recorded from PipelabTracker (the single choke point
every node transition flows through) and exposed on GET /metrics.

Three observability planes, each with a distinct job:
  traces  (tracker JSONL/SSE)  — debug one run
  metrics (this module)        — aggregate health over time
  evals   (evals/)             — answer quality over time
"""

from prometheus_client import Counter, Gauge, Histogram

# Groq llama-3.3-70b-versatile pricing (USD per million tokens);
# kept in sync with evals/run_evals.py.
COST_PER_M_INPUT = 0.59
COST_PER_M_OUTPUT = 0.79

RUNS_STARTED = Counter(
    "research_runs_started_total",
    "Research runs started",
)

RUNS_FINISHED = Counter(
    "research_runs_finished_total",
    "Research runs finished, by outcome",
    ["status"],  # completed | failed
)

ACTIVE_RUNS = Gauge(
    "research_active_runs",
    "Research runs currently executing",
)

RUN_DURATION = Histogram(
    "research_run_duration_seconds",
    "End-to-end pipeline duration",
    buckets=(5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 300),
)

NODE_DURATION = Histogram(
    "research_node_duration_seconds",
    "Per-node execution duration",
    ["node"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40, 80),
)

NODE_ERRORS = Counter(
    "research_node_errors_total",
    "Node executions that raised",
    ["node"],
)

REPLANS = Counter(
    "research_replans_total",
    "Critic verdicts that sent the graph back to the planner",
)

LLM_TOKENS = Counter(
    "research_llm_tokens_total",
    "LLM tokens consumed, by type",
    ["type"],  # prompt | completion
)

LLM_COST_USD = Counter(
    "research_llm_cost_usd_total",
    "Estimated LLM spend in USD",
)

SSE_SUBSCRIBERS = Gauge(
    "research_sse_subscribers",
    "Currently connected SSE event-stream subscribers",
)


def record_run_start() -> None:
    RUNS_STARTED.inc()
    ACTIVE_RUNS.inc()


def record_run_end(total_seconds: float, status: str, usage: dict | None) -> None:
    RUNS_FINISHED.labels(status=status).inc()
    ACTIVE_RUNS.dec()
    RUN_DURATION.observe(total_seconds)
    if usage:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        LLM_TOKENS.labels(type="prompt").inc(prompt_tokens)
        LLM_TOKENS.labels(type="completion").inc(completion_tokens)
        LLM_COST_USD.inc(
            prompt_tokens / 1e6 * COST_PER_M_INPUT
            + completion_tokens / 1e6 * COST_PER_M_OUTPUT
        )


def record_node_end(node: str, duration_ms: float, error: bool, output: dict | None) -> None:
    NODE_DURATION.labels(node=node).observe(duration_ms / 1000.0)
    if error:
        NODE_ERRORS.labels(node=node).inc()
    if node == "critic" and output and output.get("verdict") == "needs_more":
        REPLANS.inc()
