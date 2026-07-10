"""
Research workflow state for LangGraph.

Each field is populated by the corresponding node and passed forward
to the next node through the graph. All types reuse existing Pydantic
schemas so no data-model changes are required.

The state must stay serializable: it is persisted by the LangGraph
checkpointer between node transitions. Non-serializable helpers (the
Pipelab tracker) travel in the invocation config instead.
"""


from typing_extensions import TypedDict

from app.models.schemas import (
    EnhancedPrompt,
    ResearchReport,
    ResearchTask,
    TaskResult,
)


class ResearchState(TypedDict, total=False):
    """
    Shared state object that flows through the LangGraph nodes.

    Fields are populated as the graph executes:
      user_prompt      →  (input)
      enhanced_prompt  →  (prompt_enhancer node)
      tasks            →  (planner node; only the current batch)
      task_results     →  (worker node; accumulated across iterations)
      coverage_score, gaps, verdict, iteration  →  (critic node)
      report, file_path  →  (formatter node)
    """

    # Input — set by caller before graph invocation
    user_prompt: str

    # Set by prompt_enhancer node
    enhanced_prompt: EnhancedPrompt | None

    # Set by planner node — the batch of tasks for the next worker pass.
    # On replanning iterations this holds only the new gap-filling tasks.
    tasks: list[ResearchTask] | None

    # All tasks planned so far, across iterations
    all_tasks: list[ResearchTask]

    # Set by worker node — accumulated results across iterations
    task_results: list[TaskResult]

    # Set by critic node
    coverage_score: float
    gaps: list[str]
    verdict: str
    iteration: int
    max_iterations: int

    # Set by formatter node
    report: ResearchReport | None
    file_path: str | None
