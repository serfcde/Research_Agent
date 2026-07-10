"""Critic Agent - Judge research coverage and decide whether to replan."""


from app.models.schemas import EnhancedPrompt, TaskResult
from app.services.llm_service import get_llm_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

VERDICT_SUFFICIENT = "sufficient"
VERDICT_NEEDS_MORE = "needs_more"


class CriticAgent:
    """
    Agent that scores how well the collected task results cover the
    research topics, and lists the gaps worth another planning pass.
    """

    def __init__(self):
        """Initialize critic agent."""
        self.llm = get_llm_service()

    async def evaluate(
        self,
        enhanced_prompt: EnhancedPrompt,
        task_results: list[TaskResult],
    ) -> dict:
        """
        Evaluate research coverage.

        Args:
            enhanced_prompt: The structured research requirements.
            task_results: All findings gathered so far.

        Returns:
            dict with keys:
              coverage_score: float in [0, 1]
              gaps: list of missing subtopics worth researching
              verdict: "sufficient" | "needs_more"
        """
        logger.info(f"Evaluating coverage of {len(task_results)} results against {len(enhanced_prompt.topics)} topics")

        completed = [r for r in task_results if r.status in ("completed", "partial")]
        if not completed:
            # Nothing usable was gathered; another identical pass is unlikely
            # to help, so let the formatter produce what it can.
            logger.warning("Critic: no usable results, skipping replanning")
            return {"coverage_score": 0.0, "gaps": [], "verdict": VERDICT_SUFFICIENT}

        findings_digest = "\n".join(
            f"- [{r.topic} / {r.subtopic}] ({r.status}): {r.findings[:300]}"
            for r in task_results
        )

        system_prompt = """You are a rigorous research editor. Given the research requirements and the findings gathered so far, judge how completely the findings cover the requirements.

Return a JSON object with exactly these keys:
- coverage_score: number between 0 and 1 (1 = every topic and required section is well covered)
- gaps: array of short strings, each naming ONE specific missing or under-covered subtopic (empty if none). Phrase each gap as a researchable subtopic, e.g. "quantum computing hardware limitations".
- verdict: "sufficient" if the findings support a solid report, otherwise "needs_more"

Only report gaps that materially weaken the report. Do not invent gaps for well-covered areas."""

        user_message = f"""Research requirements:
Topics: {", ".join(enhanced_prompt.topics)}
Required sections: {", ".join(enhanced_prompt.required_sections)}
Focus areas: {", ".join(enhanced_prompt.focus_areas) if enhanced_prompt.focus_areas else "None"}

Findings gathered so far:
{findings_digest}"""

        try:
            parsed = await self.llm.call_llm_json(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.0,
            )

            coverage_score = float(parsed.get("coverage_score", 0.0))
            coverage_score = min(max(coverage_score, 0.0), 1.0)
            gaps = [str(g) for g in parsed.get("gaps", []) if str(g).strip()][:5]
            verdict = parsed.get("verdict", VERDICT_SUFFICIENT)
            if verdict not in (VERDICT_SUFFICIENT, VERDICT_NEEDS_MORE):
                verdict = VERDICT_SUFFICIENT
            if verdict == VERDICT_NEEDS_MORE and not gaps:
                # A replan without concrete gaps would just repeat the plan.
                verdict = VERDICT_SUFFICIENT

            logger.info(f"Critic verdict: {verdict} (coverage={coverage_score:.2f}, gaps={gaps})")
            return {"coverage_score": coverage_score, "gaps": gaps, "verdict": verdict}

        except Exception as e:
            # On judge failure, never loop — degrade to formatting what we have.
            logger.warning(f"Critic evaluation failed, treating coverage as sufficient: {str(e)}")
            return {"coverage_score": 0.0, "gaps": [], "verdict": VERDICT_SUFFICIENT}


# Singleton instance
_critic_agent = None


def get_critic() -> CriticAgent:
    """Get critic agent singleton."""
    global _critic_agent
    if _critic_agent is None:
        _critic_agent = CriticAgent()
        logger.info("Critic agent initialized")
    return _critic_agent
