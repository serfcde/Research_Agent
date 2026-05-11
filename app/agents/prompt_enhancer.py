"""Prompt Clarifier Agent - Enhance and structure user prompts."""

import json
from app.services.llm_service import get_llm_service
from app.models.schemas import EnhancedPrompt
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PromptClarifierAgent:
    """Agent for clarifying and enhancing user prompts."""

    def __init__(self):
        """Initialize prompt clarifier agent."""
        self.llm = get_llm_service()

    async def enhance_prompt(self, user_prompt: str) -> EnhancedPrompt:
        """
        Enhance user prompt with structured information.

        Args:
            user_prompt: Raw user prompt

        Returns:
            Enhanced prompt with structured data
        """
        logger.info(f"Enhancing prompt: {user_prompt[:80]}...")

        system_prompt = """You are an expert research analyst. Your job is to analyze user research prompts and structure them into actionable research requirements.

Analyze the user's prompt and extract:
1. All research topics mentioned
2. The required depth of research (quick=1 search per topic, medium=3 searches, deep=5+ searches)
3. Required sections in the report
4. Whether topics should be compared
5. Any specific focus areas

Return your analysis as a JSON object with keys: topics, research_depth, required_sections, compare_topics, focus_areas."""

        user_message = f"""Analyze this research prompt:

"{user_prompt}"

Respond with ONLY a JSON object (no markdown, no explanation)."""

        try:
            response_text = await self.llm.call_llm(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.7,
            )

            # Parse response
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning("LLM response was not valid JSON, attempting to extract...")
                # Try to extract JSON from response
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end > start:
                    parsed = json.loads(response_text[start:end])
                else:
                    raise ValueError("Could not parse LLM response as JSON")

            # Create EnhancedPrompt with defaults for missing fields
            enhanced = EnhancedPrompt(
                topics=parsed.get("topics", [user_prompt.split()[0]]),
                research_depth=parsed.get("research_depth", "medium"),
                required_sections=parsed.get(
                    "required_sections",
                    ["Overview", "Key Findings", "Challenges", "Future Trends"],
                ),
                compare_topics=parsed.get("compare_topics", len(parsed.get("topics", [])) > 1),
                focus_areas=parsed.get("focus_areas", []),
            )

            logger.info(f"Enhanced prompt with {len(enhanced.topics)} topics")
            logger.debug(f"Enhanced prompt: {enhanced.model_dump()}")

            return enhanced

        except Exception as e:
            logger.error(f"Error enhancing prompt: {str(e)}")
            # Return default enhanced prompt
            return EnhancedPrompt(
                topics=[user_prompt[:50]],
                research_depth="medium",
                required_sections=["Overview", "Key Findings", "Challenges", "Future Trends"],
                compare_topics=False,
                focus_areas=[],
            )


# Singleton instance
_clarifier_agent = None


def get_prompt_clarifier() -> PromptClarifierAgent:
    """Get prompt clarifier agent singleton."""
    global _clarifier_agent
    if _clarifier_agent is None:
        _clarifier_agent = PromptClarifierAgent()
        logger.info("Prompt clarifier agent initialized")
    return _clarifier_agent
