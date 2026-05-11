"""Planner Agent - Create research execution plans."""

import json
from typing import List
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

    async def create_plan(self, enhanced_prompt: EnhancedPrompt) -> List[ResearchTask]:
        """
        Create research plan from enhanced prompt.

        Args:
            enhanced_prompt: Enhanced prompt with structured requirements

        Returns:
            List of research tasks
        """
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

            logger.info(f"Created {len(tasks)} research tasks")
            logger.debug(f"Tasks: {[t.model_dump() for t in tasks]}")

            return tasks

        except Exception as e:
            logger.error(f"Error creating plan: {str(e)}")
            # Return default tasks
            return self._create_default_tasks(enhanced_prompt)

    def _create_default_tasks(self, enhanced_prompt: EnhancedPrompt) -> List[ResearchTask]:
        """Create default tasks if planning fails."""
        tasks = []
        task_id = 1

        for topic in enhanced_prompt.topics:
            # Overview task
            tasks.append(
                ResearchTask(
                    task_id=task_id,
                    topic=topic,
                    subtopic="overview",
                    search_query=f"{topic} overview 2026",
                    description=f"Get overview of {topic}",
                )
            )
            task_id += 1

            # Applications/Use cases
            if "applications" in " ".join(enhanced_prompt.required_sections).lower() or "findings" in " ".join(
                enhanced_prompt.required_sections
            ).lower():
                tasks.append(
                    ResearchTask(
                        task_id=task_id,
                        topic=topic,
                        subtopic="applications",
                        search_query=f"{topic} applications use cases 2026",
                        description=f"Research applications and use cases of {topic}",
                    )
                )
                task_id += 1

            # Challenges
            if "challenges" in " ".join(enhanced_prompt.required_sections).lower():
                tasks.append(
                    ResearchTask(
                        task_id=task_id,
                        topic=topic,
                        subtopic="challenges",
                        search_query=f"{topic} challenges limitations 2026",
                        description=f"Research challenges and limitations of {topic}",
                    )
                )
                task_id += 1

            # Future trends
            if "trends" in " ".join(enhanced_prompt.required_sections).lower() or "future" in " ".join(
                enhanced_prompt.required_sections
            ).lower():
                tasks.append(
                    ResearchTask(
                        task_id=task_id,
                        topic=topic,
                        subtopic="future_trends",
                        search_query=f"{topic} future trends predictions 2026",
                        description=f"Research future trends in {topic}",
                    )
                )
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
