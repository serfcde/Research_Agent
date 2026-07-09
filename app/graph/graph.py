"""
LangGraph graph definition for the Research Agent workflow.

Graph structure (linear DAG — no branching required):

  START
    │
    ▼
  prompt_enhancer  (Node 1 — PromptClarifierAgent)
    │
    ▼
  planner          (Node 2 — PlannerAgent)
    │
    ▼
  worker           (Node 3 — WorkerAgent)
    │
    ▼
  formatter        (Node 4 — FormatterAgent + FileWriter)
    │
    ▼
  END

All state transitions are tracked by PipelabTracker, which writes
structured JSON events to logs/pipelab_trace.jsonl.
"""

from langgraph.graph import StateGraph, START, END

from app.graph.state import ResearchState
from app.graph.nodes import (
    prompt_enhancer_node,
    planner_node,
    worker_node,
    formatter_node,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_research_graph() -> StateGraph:
    """
    Construct and compile the research workflow graph.

    Returns a compiled LangGraph that accepts a ResearchState and
    executes the four agent nodes in sequence.
    """
    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("prompt_enhancer", prompt_enhancer_node)
    graph.add_node("planner",         planner_node)
    graph.add_node("worker",          worker_node)
    graph.add_node("formatter",       formatter_node)

    # Wire edges: START → node1 → node2 → node3 → node4 → END
    graph.add_edge(START,             "prompt_enhancer")
    graph.add_edge("prompt_enhancer", "planner")
    graph.add_edge("planner",         "worker")
    graph.add_edge("worker",          "formatter")
    graph.add_edge("formatter",        END)

    compiled = graph.compile()
    logger.info("Research workflow graph compiled (4 nodes, linear DAG)")
    return compiled


# Module-level singleton — compiled once on first import
_graph = None


def get_research_graph():
    """Return the compiled graph singleton."""
    global _graph
    if _graph is None:
        _graph = build_research_graph()
    return _graph
