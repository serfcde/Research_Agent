# Architecture

## The pipeline

The research workflow is a **LangGraph `StateGraph` with a cycle**:

```
START → prompt_enhancer → planner → worker → critic ──┬→ formatter → END
                             ▲                        │
                             └── gaps, iteration < 2 ─┘
```

| Node | Agent | Responsibility |
|---|---|---|
| `prompt_enhancer` | `PromptClarifierAgent` | Parse the raw prompt into topics, depth, required sections (LLM + heuristic fallback) |
| `planner` | `PlannerAgent` | Full research plan on first pass; **incremental gap-filling tasks** (fresh ids, duplicate-query skip) when re-entered by the critic |
| `worker` | `WorkerAgent` | Executes the task batch concurrently (semaphore-bounded Tavily searches + LLM summarisation); accumulates results across iterations |
| `critic` | `CriticAgent` | Judges coverage (temperature 0), emits `{coverage_score, gaps, verdict}`; the conditional edge routes back to `planner` or on to `formatter`. Hard-capped at `max_iterations = 2`; judge failure never loops |
| `formatter` | `FormatterAgent` | Synthesises all accumulated results into a cited report and writes the .txt |

State (`app/graph/state.py`) is a serializable TypedDict — the tracker travels in the **invocation config**, not state, so checkpointing stays clean.

## Durability

- **Checkpointing** — with `DATABASE_URL` set, the graph compiles with `AsyncPostgresSaver`; every node transition persists state under `thread_id = run_id`.
- **Run store** (`app/services/run_store.py`) — `runs` table records prompt/status/report; an in-memory implementation with the same interface backs local dev and tests.
- **Background jobs** — `POST /api/research` inserts a run row, launches the pipeline with `asyncio.create_task`, and returns `202 {run_id}`.
- **Crash recovery** — on startup, `resume_interrupted_runs()` finds runs stuck in `running` and re-invokes the graph with `None` input, which continues from the last checkpoint (`app/services/orchestration.py`). A run SIGKILLed mid-`worker` resumes at `worker` after restart.

## Failure-mode design

Every LLM-dependent step has a non-LLM fallback so a rate limit degrades quality instead of killing the run:

- prompt enhancement → heuristic topic extraction
- planning → templated default tasks; gap planning → gap names as search queries
- summarisation → raw source snippets (`status: partial`)
- critic → "sufficient" verdict (never loops on judge failure)
- search → Tavily → SerpAPI fallback → empty result (report notes the gap)

## Observability

`PipelabTracker` (`app/graph/tracker.py`) emits `run_start / node_start / node_end / run_end` events with input/output summaries, durations, iteration numbers, and real token usage (from Groq `response.usage`, accumulated per-run via a contextvar). Each event goes to:

1. `logs/pipelab_trace.jsonl` — durable trace, consumed by the eval harness for ops metrics and by SSE replay;
2. an in-process **per-run `asyncio.Queue` bus** — live SSE streaming to the frontend.

**Trace correlation:** the frontend generates the run id, sends it as `X-Trace-Id`, and the backend uses it as run id *and* checkpointer thread id. The Next.js events route (`frontend/app/api/research/[id]/events/route.ts`) is a thin proxy that rebuilds a span tree from the streamed node events, so the workflow graph in the UI mirrors actual backend execution — including replan cycles.

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/research` | Start a run → `202 {run_id}` (rate-limited 5/min) |
| `GET /api/research/{id}` | Status + report from the durable store |
| `GET /api/research/{id}/events` | SSE: replay + live node transitions |
| `GET /api/runs` | Run history |
| `POST /api/enhance-prompt`, `/plan-research`, `/execute-research`, `/format-report` | Per-agent endpoints for debugging/tests |
| `GET /health` | Liveness + Postgres ping (503 when degraded) |

Auth: `X-API-Key` against the comma-separated `API_KEYS` setting (empty disables auth; `/api/status` and `/health` stay public).

## Optional: Pipelock LLM-traffic proxy

For local monitoring, all Groq/Tavily traffic can be routed through a [Pipelock](https://github.com/pipelab-ai/pipelock) forward proxy (DLP, prompt-injection scanning, flight recorder). Set `PIPELOCK_PROXY_URL`; TLS verification stays on unless `PIPELOCK_PROXY_INSECURE=true` is explicitly set for a local TLS-terminating proxy. Off by default and not used in deployment.
