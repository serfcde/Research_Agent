"""Pydantic models for data validation and serialization."""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# Prompt Clarifier Agent
# ============================================================================


class EnhancedPrompt(BaseModel):
    """Enhanced user prompt with structured research requirements."""

    topics: List[str] = Field(..., description="List of research topics extracted from user prompt")
    research_depth: str = Field(default="medium", description="Depth of research: quick, medium, or deep")
    required_sections: List[str] = Field(
        default=["Overview", "Key Findings", "Challenges", "Future Trends"],
        description="Required sections in the research report",
    )
    compare_topics: bool = Field(default=False, description="Whether to include comparative analysis")
    focus_areas: List[str] = Field(default=[], description="Specific areas to focus on")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topics": ["Quantum Computing", "Edge AI"],
                "research_depth": "medium",
                "required_sections": ["Overview", "Applications", "Challenges", "Future Trends"],
                "compare_topics": True,
                "focus_areas": ["Industry adoption", "Technical challenges"],
            }
        }
    )


# ============================================================================
# Planner Agent
# ============================================================================


class ResearchTask(BaseModel):
    """Individual research task to be executed."""

    task_id: int = Field(..., description="Unique task identifier")
    topic: str = Field(..., description="Topic for this task")
    subtopic: str = Field(..., description="Specific subtopic or aspect")
    search_query: str = Field(..., description="Query to use for web search")
    description: str = Field(..., description="Human-readable description of the task")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": 1,
                "topic": "Quantum Computing",
                "subtopic": "latest_applications",
                "search_query": "quantum computing applications 2026",
                "description": "Fetch latest quantum computing applications and use cases",
            }
        }
    )


# ============================================================================
# Worker Agent
# ============================================================================


class ResearchSource(BaseModel):
    """Individual source of research information."""

    title: str = Field(..., description="Source title")
    url: str = Field(..., description="Source URL")
    snippet: str = Field(..., description="Brief excerpt from source")


class TaskResult(BaseModel):
    """Result from executing a single research task."""

    task_id: int = Field(..., description="Original task ID")
    topic: str = Field(..., description="Research topic")
    subtopic: str = Field(..., description="Specific subtopic")
    status: str = Field(default="completed", description="Execution status: completed, failed, partial")
    findings: str = Field(..., description="Summarized findings (200-300 words)")
    sources: List[ResearchSource] = Field(default=[], description="List of sources used")
    execution_time_seconds: float = Field(..., description="Time taken to execute this task")
    error_message: Optional[str] = Field(default=None, description="Error message if task failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": 1,
                "topic": "Quantum Computing",
                "subtopic": "latest_applications",
                "status": "completed",
                "findings": "Recent quantum computing applications...",
                "sources": [
                    {
                        "title": "Quantum Computing Breakthroughs",
                        "url": "https://example.com",
                        "snippet": "Recent developments in quantum...",
                    }
                ],
                "execution_time_seconds": 12.5,
                "error_message": None,
            }
        }
    )


# ============================================================================
# Formatter Agent
# ============================================================================


class ResearchReport(BaseModel):
    """Structured research report."""

    title: str = Field(..., description="Report title")
    topics: List[str] = Field(..., description="Research topics covered")
    introduction: str = Field(..., description="Report introduction")
    sections: Dict[str, str] = Field(..., description="Report sections by topic")
    comparative_analysis: Optional[str] = Field(default=None, description="Comparative analysis if multi-topic")
    conclusion: str = Field(..., description="Report conclusion")
    citations: List[ResearchSource] = Field(default=[], description="All cited sources")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation timestamp")
    total_words: int = Field(..., description="Total word count")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Research Report: Quantum Computing and Edge AI",
                "topics": ["Quantum Computing", "Edge AI"],
                "introduction": "This report explores...",
                "sections": {"Quantum Computing": "Overview: ...", "Edge AI": "Overview: ..."},
                "comparative_analysis": "Both technologies...",
                "conclusion": "In conclusion...",
                "citations": [],
                "generated_at": "2026-05-11T12:30:00",
                "total_words": 3500,
            }
        }
    )


# ============================================================================
# API Request/Response Models
# ============================================================================


MAX_PROMPT_LENGTH = 2000


def _validate_prompt(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("prompt must not be empty")
    return stripped


class PromptEnhancementRequest(BaseModel):
    """Request to enhance user prompt."""

    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH, description="User prompt to enhance")

    _strip_prompt = field_validator("prompt")(_validate_prompt)


class PlanningRequest(BaseModel):
    """Request to create research plan."""

    enhanced_prompt: EnhancedPrompt = Field(..., description="Enhanced prompt from clarifier")


class ExecutionRequest(BaseModel):
    """Request to execute research tasks."""

    tasks: List[ResearchTask] = Field(..., description="Tasks to execute")


class FormattingRequest(BaseModel):
    """Request to format research results."""

    task_results: List[TaskResult] = Field(..., description="Results from executed tasks")
    enhanced_prompt: EnhancedPrompt = Field(..., description="Original enhanced prompt")


class FullResearchRequest(BaseModel):
    """Full end-to-end research request."""

    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH, description="User research prompt")

    _strip_prompt = field_validator("prompt")(_validate_prompt)

    model_config = ConfigDict(
        json_schema_extra={"example": {"prompt": "Research AI in healthcare and blockchain in banking"}}
    )


class FullResearchResponse(BaseModel):
    """Full end-to-end research response."""

    report: ResearchReport = Field(..., description="Generated research report")
    file_path: str = Field(..., description="Path to saved TXT report")
    status: str = Field(default="completed", description="Overall status")
    total_execution_time_seconds: float = Field(..., description="Total execution time")
