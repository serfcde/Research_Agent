"""
LangGraph node functions.

Each function is a thin wrapper around an existing agent class.
Nodes receive the shared ResearchState plus the invocation config;
the Pipelab tracker travels in config["configurable"]["tracker"]
(NOT in state) so checkpointed state stays serializable.

Node execution order (defined in graph.py):

  prompt_enhancer → planner → worker → critic ─┬→ formatter
                       ▲                        │
                       └── (gaps, iteration < max_iterations)
"""

from langchain_core.runnables import RunnableConfig

from app.agents.prompt_enhancer import get_prompt_clarifier
from app.agents.planner import get_planner
from app.agents.worker import get_worker
from app.agents.critic import get_critic, VERDICT_NEEDS_MORE
from app.agents.formatter import get_formatter
from app.tools.file_writer import get_file_writer
from app.graph.state import ResearchState
from app.graph.tracker import PipelabTracker
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_ITERATIONS = 2


def _tracker_from_config(config: RunnableConfig) -> PipelabTracker:
    tracker = (config.get("configurable") or {}).get("tracker")
    return tracker if tracker is not None else PipelabTracker(run_id="untracked")


# --------------------------------------------------------------------------- #
# Node 1 — Prompt Enhancer                                                    #
# --------------------------------------------------------------------------- #

async def prompt_enhancer_node(state: ResearchState, config: RunnableConfig) -> ResearchState:
    """
    Clarify and enrich the raw user prompt.

    Reads:   user_prompt
    Writes:  enhanced_prompt
    """
    tracker = _tracker_from_config(config)
    user_prompt = state["user_prompt"]

    start_ts = tracker.emit_node_start(
        "prompt_enhancer",
        input_summary={"user_prompt": user_prompt[:120]},
    )

    try:
        agent = get_prompt_clarifier()
        enhanced = await agent.enhance_prompt(user_prompt)

        tracker.emit_node_end(
            "prompt_enhancer",
            start_ts,
            output_summary={
                "topics": enhanced.topics,
                "research_depth": enhanced.research_depth,
            },
        )
        logger.info(f"[Graph] prompt_enhancer → {len(enhanced.topics)} topics: {enhanced.topics}")
        return {"enhanced_prompt": enhanced}

    except Exception as exc:
        tracker.emit_node_end("prompt_enhancer", start_ts, error=str(exc))
        raise


# --------------------------------------------------------------------------- #
# Node 2 — Planner                                                            #
# --------------------------------------------------------------------------- #

async def planner_node(state: ResearchState, config: RunnableConfig) -> ResearchState:
    """
    Break the enhanced prompt into a batch of search tasks.

    On the first pass this plans the full research. When the critic sent
    us back with gaps, it plans only incremental gap-filling tasks.

    Reads:   enhanced_prompt, gaps, all_tasks
    Writes:  tasks (current batch), all_tasks (accumulated)
    """
    tracker = _tracker_from_config(config)
    enhanced_prompt = state["enhanced_prompt"]
    gaps = state.get("gaps") or []
    all_tasks = state.get("all_tasks") or []
    iteration = state.get("iteration", 0)

    start_ts = tracker.emit_node_start(
        "planner",
        input_summary={
            "topics": enhanced_prompt.topics,
            "depth": enhanced_prompt.research_depth,
            "gaps": gaps,
            "iteration": iteration,
        },
    )

    try:
        agent = get_planner()
        if gaps and all_tasks:
            batch = await agent.create_plan(enhanced_prompt, gaps=gaps, existing_tasks=all_tasks)
        else:
            batch = await agent.create_plan(enhanced_prompt)

        tracker.emit_node_end(
            "planner",
            start_ts,
            output_summary={
                "task_count": len(batch),
                "iteration": iteration,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "topic": t.topic,
                        "subtopic": t.subtopic,
                        "search_query": t.search_query,
                        "description": t.description,
                    }
                    for t in batch[:10]
                ],
            },
        )
        logger.info(f"[Graph] planner → {len(batch)} tasks (iteration {iteration})")
        return {
            "tasks": batch,
            "all_tasks": all_tasks + batch,
            # Consume the gaps so a future pass doesn't re-plan them.
            "gaps": [],
        }

    except Exception as exc:
        tracker.emit_node_end("planner", start_ts, error=str(exc))
        raise


# --------------------------------------------------------------------------- #
# Node 3 — Worker                                                             #
# --------------------------------------------------------------------------- #

async def worker_node(state: ResearchState, config: RunnableConfig) -> ResearchState:
    """
    Execute the current task batch concurrently via web search + LLM
    summarisation, accumulating results across iterations.

    Reads:   tasks, task_results
    Writes:  task_results (accumulated)
    """
    tracker = _tracker_from_config(config)
    tasks = state.get("tasks") or []
    previous_results = state.get("task_results") or []
    iteration = state.get("iteration", 0)

    start_ts = tracker.emit_node_start(
        "worker",
        input_summary={"task_count": len(tasks), "iteration": iteration},
    )

    try:
        agent = get_worker()
        results = await agent.execute_tasks(tasks) if tasks else []

        completed = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "failed")
        queries = {t.task_id: t.search_query for t in tasks}

        tracker.emit_node_end(
            "worker",
            start_ts,
            output_summary={
                "total": len(results),
                "completed": completed,
                "failed": failed,
                "iteration": iteration,
                "results": [
                    {
                        "task_id": r.task_id,
                        "topic": r.topic,
                        "subtopic": r.subtopic,
                        "search_query": queries.get(r.task_id, ""),
                        "status": r.status,
                        "sources": len(r.sources),
                        "seconds": round(r.execution_time_seconds, 2),
                        "findings_preview": r.findings[:200],
                    }
                    for r in results[:10]
                ],
            },
        )
        logger.info(f"[Graph] worker → {completed}/{len(results)} tasks completed (iteration {iteration})")
        return {"task_results": previous_results + results}

    except Exception as exc:
        tracker.emit_node_end("worker", start_ts, error=str(exc))
        raise


# --------------------------------------------------------------------------- #
# Node 4 — Critic                                                             #
# --------------------------------------------------------------------------- #

async def critic_node(state: ResearchState, config: RunnableConfig) -> ResearchState:
    """
    Judge coverage of the accumulated results and decide whether another
    planning pass is worth it.

    Reads:   enhanced_prompt, task_results, iteration, max_iterations
    Writes:  coverage_score, gaps, verdict, iteration
    """
    tracker = _tracker_from_config(config)
    enhanced_prompt = state["enhanced_prompt"]
    task_results = state.get("task_results") or []
    iteration = state.get("iteration", 0) + 1
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)

    start_ts = tracker.emit_node_start(
        "critic",
        input_summary={"result_count": len(task_results), "iteration": iteration},
    )

    try:
        agent = get_critic()
        evaluation = await agent.evaluate(enhanced_prompt, task_results)

        verdict = evaluation["verdict"]
        if verdict == VERDICT_NEEDS_MORE and iteration >= max_iterations:
            logger.info(f"[Graph] critic wanted more research but iteration cap ({max_iterations}) reached")
            verdict = "sufficient"

        tracker.emit_node_end(
            "critic",
            start_ts,
            output_summary={
                "coverage_score": evaluation["coverage_score"],
                "gaps": evaluation["gaps"],
                "verdict": verdict,
                "iteration": iteration,
            },
        )
        logger.info(
            f"[Graph] critic → {verdict} (coverage={evaluation['coverage_score']:.2f}, iteration {iteration})"
        )
        return {
            "coverage_score": evaluation["coverage_score"],
            "gaps": evaluation["gaps"] if verdict == VERDICT_NEEDS_MORE else [],
            "verdict": verdict,
            "iteration": iteration,
        }

    except Exception as exc:
        tracker.emit_node_end("critic", start_ts, error=str(exc))
        raise


def route_after_critic(state: ResearchState) -> str:
    """Conditional edge: replan when the critic found actionable gaps."""
    if state.get("verdict") == VERDICT_NEEDS_MORE and state.get("gaps"):
        return "planner"
    return "formatter"


# --------------------------------------------------------------------------- #
# Node 5 — Formatter                                                          #
# --------------------------------------------------------------------------- #

async def formatter_node(state: ResearchState, config: RunnableConfig) -> ResearchState:
    """
    Synthesise all accumulated results into a structured report and save it.

    Reads:   task_results, enhanced_prompt
    Writes:  report, file_path
    """
    tracker = _tracker_from_config(config)
    task_results = state.get("task_results") or []
    enhanced_prompt = state["enhanced_prompt"]

    start_ts = tracker.emit_node_start(
        "formatter",
        input_summary={"result_count": len(task_results)},
    )

    try:
        # Format the report
        agent = get_formatter()
        report = await agent.format_report(task_results, enhanced_prompt)

        # Save report to .txt
        report_text = agent.report_to_text(report)
        file_writer = get_file_writer()
        file_path = file_writer.save_report_txt(
            report_text,
            topic="_".join(enhanced_prompt.topics[:2]),
        )

        tracker.emit_node_end(
            "formatter",
            start_ts,
            output_summary={
                "total_words": report.total_words,
                "citations": len(report.citations),
                "file_path": str(file_path),
            },
        )
        logger.info(f"[Graph] formatter → {report.total_words} words, saved to {file_path}")
        return {"report": report, "file_path": str(file_path)}

    except Exception as exc:
        tracker.emit_node_end("formatter", start_ts, error=str(exc))
        raise
