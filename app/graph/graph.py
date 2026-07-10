"""
LangGraph graph definition for the Research Agent workflow.

Graph structure (cyclic — the critic can send the flow back to the
planner for gap-filling passes, capped by max_iterations):

  START
    │
    ▼
  prompt_enhancer  (PromptClarifierAgent)
    │
    ▼
  planner          (PlannerAgent — full plan, or gap plan on re-entry)
    │
    ▼
  worker           (WorkerAgent — accumulates results)
    │
    ▼
  critic           (CriticAgent — coverage judge)
    │ verdict=needs_more ∧ gaps ∧ iteration < max_iterations
    ├────────────────────────────► planner  (replan loop)
    │ otherwise
    ▼
  formatter        (FormatterAgent + FileWriter)
    │
    ▼
  END

State transitions are tracked by PipelabTracker (passed via the
invocation config), which writes structured JSON events to
logs/pipelab_trace.jsonl and streams them to SSE subscribers.

When settings.database_url is set, graph state is checkpointed to
Postgres (thread_id = run_id) so runs survive process restarts.
"""

from typing import Optional

from langgraph.graph import StateGraph, START, END

from app.config.settings import settings
from app.graph.state import ResearchState
from app.graph.nodes import (
    prompt_enhancer_node,
    planner_node,
    worker_node,
    critic_node,
    formatter_node,
    route_after_critic,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_graph_builder() -> StateGraph:
    """Construct the (uncompiled) research workflow graph."""
    graph = StateGraph(ResearchState)

    graph.add_node("prompt_enhancer", prompt_enhancer_node)
    graph.add_node("planner", planner_node)
    graph.add_node("worker", worker_node)
    graph.add_node("critic", critic_node)
    graph.add_node("formatter", formatter_node)

    graph.add_edge(START, "prompt_enhancer")
    graph.add_edge("prompt_enhancer", "planner")
    graph.add_edge("planner", "worker")
    graph.add_edge("worker", "critic")
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {"planner": "planner", "formatter": "formatter"},
    )
    graph.add_edge("formatter", END)

    return graph


# Module-level singletons — the compiled graph and, when Postgres is
# configured, the checkpointer context manager kept open for the app's
# lifetime (closed via aclose_graph on shutdown).
_graph = None
_checkpointer_cm: Optional[object] = None


async def get_research_graph():
    """
    Return the compiled graph singleton.

    With DATABASE_URL configured the graph is compiled with an
    AsyncPostgresSaver checkpointer; otherwise it runs uncheckpointed
    (tests, local dev without Postgres).
    """
    global _graph, _checkpointer_cm
    if _graph is None:
        builder = build_graph_builder()

        if settings.database_url:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            _checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
            checkpointer = await _checkpointer_cm.__aenter__()
            await checkpointer.setup()
            _graph = builder.compile(checkpointer=checkpointer)
            logger.info("Research graph compiled with Postgres checkpointing (5 nodes, critic loop)")
        else:
            _graph = builder.compile()
            logger.info("Research graph compiled without checkpointing (5 nodes, critic loop)")

    return _graph


async def aclose_graph() -> None:
    """Release the checkpointer connection on app shutdown."""
    global _graph, _checkpointer_cm
    if _checkpointer_cm is not None:
        try:
            await _checkpointer_cm.__aexit__(None, None, None)
        except Exception as exc:
            logger.warning(f"Error closing checkpointer: {exc}")
        _checkpointer_cm = None
    _graph = None
