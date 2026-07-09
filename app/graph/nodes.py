"""
LangGraph node functions.

Each function is a thin wrapper around an existing agent class.
The agents themselves are NOT modified — only the calling convention
changes from direct method calls to LangGraph node signatures
(receive state dict → return partial state update).

Node execution order (defined in graph.py):
  prompt_enhancer  →  planner  →  worker  →  formatter
"""

from app.agents.prompt_enhancer import get_prompt_clarifier
from app.agents.planner import get_planner
from app.agents.worker import get_worker
from app.agents.formatter import get_formatter
from app.tools.file_writer import get_file_writer
from app.graph.state import ResearchState
from app.graph.tracker import PipelabTracker
from app.utils.logger import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Node 1 — Prompt Enhancer                                                    #
# --------------------------------------------------------------------------- #

async def prompt_enhancer_node(state: ResearchState) -> ResearchState:
    """
    Node 1: Clarify and enrich the raw user prompt.

    Reads:   state["user_prompt"]
    Writes:  state["enhanced_prompt"]
    """
    tracker: PipelabTracker = state["_tracker"]  # injected by orchestrator
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

async def planner_node(state: ResearchState) -> ResearchState:
    """
    Node 2: Break the enhanced prompt into a list of search tasks.

    Reads:   state["enhanced_prompt"]
    Writes:  state["tasks"]
    """
    tracker: PipelabTracker = state["_tracker"]
    enhanced_prompt = state["enhanced_prompt"]

    start_ts = tracker.emit_node_start(
        "planner",
        input_summary={
            "topics": enhanced_prompt.topics,
            "depth": enhanced_prompt.research_depth,
        },
    )

    try:
        agent = get_planner()
        tasks = await agent.create_plan(enhanced_prompt)

        tracker.emit_node_end(
            "planner",
            start_ts,
            output_summary={"task_count": len(tasks)},
        )
        logger.info(f"[Graph] planner → {len(tasks)} tasks")
        return {"tasks": tasks}

    except Exception as exc:
        tracker.emit_node_end("planner", start_ts, error=str(exc))
        raise


# --------------------------------------------------------------------------- #
# Node 3 — Worker                                                             #
# --------------------------------------------------------------------------- #

async def worker_node(state: ResearchState) -> ResearchState:
    """
    Node 3: Execute all tasks concurrently via web search + LLM summarisation.

    Reads:   state["tasks"]
    Writes:  state["task_results"]
    """
    tracker: PipelabTracker = state["_tracker"]
    tasks = state["tasks"]

    start_ts = tracker.emit_node_start(
        "worker",
        input_summary={"task_count": len(tasks)},
    )

    try:
        agent = get_worker()
        results = await agent.execute_tasks(tasks)

        completed = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "failed")

        tracker.emit_node_end(
            "worker",
            start_ts,
            output_summary={
                "total": len(results),
                "completed": completed,
                "failed": failed,
            },
        )
        logger.info(f"[Graph] worker → {completed}/{len(results)} tasks completed")
        return {"task_results": results}

    except Exception as exc:
        tracker.emit_node_end("worker", start_ts, error=str(exc))
        raise


# --------------------------------------------------------------------------- #
# Node 4 — Formatter                                                          #
# --------------------------------------------------------------------------- #

async def formatter_node(state: ResearchState) -> ResearchState:
    """
    Node 4: Synthesise task results into a structured report and save to .txt.

    Reads:   state["task_results"], state["enhanced_prompt"]
    Writes:  state["report"], state["file_path"]
    """
    tracker: PipelabTracker = state["_tracker"]
    task_results = state["task_results"]
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
