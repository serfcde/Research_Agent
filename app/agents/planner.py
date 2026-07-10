"""Planner Agent - Create research execution plans."""

import json
from typing import List, Optional
from app.services.llm_service import get_llm_service
from app.models.schemas import EnhancedPrompt, ResearchTask
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PlannerAgent:
    """Agent for creating research execution plans."""

    def __init__(self):
        """Initialize planner agent."""
        self.llm = get_llm_service()
        self.task_id_counter = 0

    async def create_plan(
        self,
        enhanced_prompt: EnhancedPrompt,
        gaps: Optional[List[str]] = None,
        existing_tasks: Optional[List[ResearchTask]] = None,
    ) -> List[ResearchTask]:
        """
        Create research plan from enhanced prompt.

        Args:
            enhanced_prompt: Enhanced prompt with structured requirements
            gaps: When replanning, the specific under-covered subtopics to
                target. Only incremental gap-filling tasks are returned.
            existing_tasks: Tasks from earlier iterations, used to avoid
                duplicates and to continue task numbering.

        Returns:
            List of research tasks (only the new ones when gaps are given)
        """
        if gaps:
            return await self._create_gap_plan(enhanced_prompt, gaps, existing_tasks or [])

        logger.info(f"Creating plan for {len(enhanced_prompt.topics)} topics")

        system_prompt = """You are an expert research planner. Your job is to break down research requirements into specific, actionable tasks.

For each topic and section combination, create a research task with:
- A descriptive name/subtopic
- A specific search query that will find relevant information
- A brief description of what to research

Research depth levels:
- quick: 1 task per topic
- medium: 3-4 tasks per topic (overview, applications, challenges/trends)
- deep: 5-6 tasks per topic (overview, applications, challenges, future trends, comparison, implementations)

Return a JSON array of tasks with fields: subtopic, search_query, description."""

        topics_list = ", ".join(enhanced_prompt.topics)
        sections_list = ", ".join(enhanced_prompt.required_sections)

        user_message = f"""Create a research plan for:

Topics: {topics_list}
Depth: {enhanced_prompt.research_depth}
Required Sections: {sections_list}
Compare Topics: {enhanced_prompt.compare_topics}
Focus Areas: {', '.join(enhanced_prompt.focus_areas) if enhanced_prompt.focus_areas else 'None'}

Generate specific research tasks with search queries. For each topic, create tasks to cover all required sections."""

        try:
            response_text = await self.llm.call_llm(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.7,
            )

            # Parse response
            try:
                tasks_data = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning("LLM response was not valid JSON, attempting to extract...")
                start = response_text.find("[")
                end = response_text.rfind("]") + 1
                if start != -1 and end > start:
                    tasks_data = json.loads(response_text[start:end])
                else:
                    # Fallback: create default tasks
                    tasks_data = self._create_default_tasks(enhanced_prompt)

            # Convert to ResearchTask objects
            tasks = []
            for idx, task_data in enumerate(tasks_data, 1):
                task = ResearchTask(
                    task_id=idx,
                    topic=task_data.get("topic", enhanced_prompt.topics[0]),
                    subtopic=task_data.get("subtopic", "research"),
                    search_query=task_data.get("search_query", f"research {task_data.get('subtopic', 'info')} 2026"),
                    description=task_data.get("description", "Research task"),
                )
                tasks.append(task)

            tasks = self._limit_tasks_by_depth(tasks, enhanced_prompt)

            logger.info(f"Created {len(tasks)} research tasks")
            logger.debug(f"Tasks: {[t.model_dump() for t in tasks]}")

            return tasks

        except Exception as e:
            logger.error(f"Error creating plan: {str(e)}")
            # Return default tasks
            return self._create_default_tasks(enhanced_prompt)

    async def _create_gap_plan(
        self,
        enhanced_prompt: EnhancedPrompt,
        gaps: List[str],
        existing_tasks: List[ResearchTask],
    ) -> List[ResearchTask]:
        """Create incremental tasks that target specific coverage gaps."""
        logger.info(f"Replanning for {len(gaps)} coverage gaps")

        next_task_id = max((t.task_id for t in existing_tasks), default=0) + 1
        existing_queries = {t.search_query.strip().lower() for t in existing_tasks}

        system_prompt = """You are an expert research planner. Earlier research left specific coverage gaps. Create ONE research task per gap.

Return a JSON array of tasks with fields: topic, subtopic, search_query, description.
- topic must be one of the original research topics the gap belongs to
- search_query must be a specific web search likely to close the gap
- Do NOT repeat research that was already done."""

        user_message = f"""Original topics: {", ".join(enhanced_prompt.topics)}

Coverage gaps to close:
{chr(10).join(f"- {gap}" for gap in gaps)}

Searches already performed (do not repeat):
{chr(10).join(f"- {t.search_query}" for t in existing_tasks)}"""

        try:
            response_text = await self.llm.call_llm(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.3,
            )
            try:
                tasks_data = json.loads(response_text)
            except json.JSONDecodeError:
                start = response_text.find("[")
                end = response_text.rfind("]") + 1
                if start == -1 or end <= start:
                    raise ValueError("Could not parse gap plan as JSON")
                tasks_data = json.loads(response_text[start:end])
        except Exception as e:
            logger.warning(f"Gap planning via LLM failed ({str(e)}), using gap names as queries")
            tasks_data = [
                {
                    "subtopic": f"gap_{idx}",
                    "search_query": f"{gap} 2026",
                    "description": f"Close coverage gap: {gap}",
                }
                for idx, gap in enumerate(gaps, 1)
            ]

        tasks = []
        for task_data in tasks_data[: len(gaps)]:
            query = str(task_data.get("search_query", "")).strip()
            if not query or query.lower() in existing_queries:
                continue
            tasks.append(
                ResearchTask(
                    task_id=next_task_id + len(tasks),
                    topic=task_data.get("topic", enhanced_prompt.topics[0]),
                    subtopic=task_data.get("subtopic", "gap_research"),
                    search_query=query,
                    description=task_data.get("description", "Gap-filling research task"),
                )
            )

        logger.info(f"Created {len(tasks)} gap-filling tasks")
        return tasks

    def _limit_tasks_by_depth(
        self,
        tasks: List[ResearchTask],
        enhanced_prompt: EnhancedPrompt,
    ) -> List[ResearchTask]:
        """Keep task counts aligned with the selected research depth."""
        max_per_topic = {
            "quick": 1,
            "medium": 3,
            "deep": 6,
        }.get(enhanced_prompt.research_depth, 3)

        limited = []
        per_topic_counts = {topic: 0 for topic in enhanced_prompt.topics}

        for task in tasks:
            topic = task.topic if task.topic in per_topic_counts else enhanced_prompt.topics[0]
            if per_topic_counts[topic] >= max_per_topic:
                continue
            per_topic_counts[topic] += 1
            limited.append(task.model_copy(update={"task_id": len(limited) + 1, "topic": topic}))

        if not limited:
            return self._create_default_tasks(enhanced_prompt)

        return limited

    def _create_default_tasks(self, enhanced_prompt: EnhancedPrompt) -> List[ResearchTask]:
        """Create default tasks if planning fails."""
        tasks = []
        task_id = 1
        max_per_topic = {
            "quick": 1,
            "medium": 3,
            "deep": 6,
        }.get(enhanced_prompt.research_depth, 3)

        for topic in enhanced_prompt.topics:
            topic_tasks = []
            # Overview task
            topic_tasks.append(
                ResearchTask(
                    task_id=task_id,
                    topic=topic,
                    subtopic="overview",
                    search_query=f"{topic} overview 2026",
                    description=f"Get overview of {topic}",
                )
            )

            # Applications/Use cases
            if "applications" in " ".join(enhanced_prompt.required_sections).lower() or "findings" in " ".join(
                enhanced_prompt.required_sections
            ).lower():
                topic_tasks.append(
                    ResearchTask(
                        task_id=task_id,
                        topic=topic,
                        subtopic="applications",
                        search_query=f"{topic} applications use cases 2026",
                        description=f"Research applications and use cases of {topic}",
                    )
                )

            # Challenges
            if "challenges" in " ".join(enhanced_prompt.required_sections).lower():
                topic_tasks.append(
                    ResearchTask(
                        task_id=task_id,
                        topic=topic,
                        subtopic="challenges",
                        search_query=f"{topic} challenges limitations 2026",
                        description=f"Research challenges and limitations of {topic}",
                    )
                )

            # Future trends
            if "trends" in " ".join(enhanced_prompt.required_sections).lower() or "future" in " ".join(
                enhanced_prompt.required_sections
            ).lower():
                topic_tasks.append(
                    ResearchTask(
                        task_id=task_id,
                        topic=topic,
                        subtopic="future_trends",
                        search_query=f"{topic} future trends predictions 2026",
                        description=f"Research future trends in {topic}",
                    )
                )

            for task in topic_tasks[:max_per_topic]:
                tasks.append(task.model_copy(update={"task_id": task_id}))
                task_id += 1

        return tasks


# Singleton instance
_planner_agent = None


def get_planner() -> PlannerAgent:
    """Get planner agent singleton."""
    global _planner_agent
    if _planner_agent is None:
        _planner_agent = PlannerAgent()
        logger.info("Planner agent initialized")
    return _planner_agent
