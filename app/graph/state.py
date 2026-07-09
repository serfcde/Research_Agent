"""
Research workflow state for LangGraph.

Each field is populated by the corresponding node and passed forward
to the next node through the graph. All types reuse existing Pydantic
schemas so no data-model changes are required.
"""

from typing import List, Optional
from typing_extensions import TypedDict

from app.models.schemas import (
    EnhancedPrompt,
    ResearchTask,
    TaskResult,
    ResearchReport,
)


class ResearchState(TypedDict, total=False):
    """
    Shared state object that flows through the LangGraph nodes.

    Fields are populated sequentially:
      user_prompt  →  (prompt_enhancer node)
      enhanced_prompt  →  (planner node)
      tasks  →  (worker node)
      task_results  →  (formatter node)
      report, file_path  →  (returned to caller)
    """

    # Input — set by caller before graph invocation
    user_prompt: str

    # Set by prompt_enhancer node
    enhanced_prompt: Optional[EnhancedPrompt]

    # Set by planner node
    tasks: Optional[List[ResearchTask]]

    # Set by worker node
    task_results: Optional[List[TaskResult]]

    # Set by formatter node
    report: Optional[ResearchReport]
    file_path: Optional[str]

    # Populated at every node transition — consumed by PipelabTracker
    execution_events: List[dict]
