"""Formatter Agent - Create professional research reports."""

from app.models.schemas import (
    EnhancedPrompt,
    ResearchReport,
    ResearchSource,
    TaskResult,
)
from app.services.llm_service import get_llm_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FormatterAgent:
    """Agent for formatting research results into professional reports."""

    def __init__(self):
        """Initialize formatter agent."""
        self.llm = get_llm_service()

    def _group_results_by_topic(self, results: list[TaskResult]) -> dict[str, list[TaskResult]]:
        """Group task results by topic, case-insensitive, keeping original casing for display."""
        grouped: dict[str, list[TaskResult]] = {}
        canonical: dict[str, str] = {}
        for result in results:
            normalized = result.topic.strip().lower()
            key = canonical.setdefault(normalized, result.topic.strip())
            grouped.setdefault(key, []).append(result)
        return grouped

    @staticmethod
    def _results_for_topic(grouped: dict[str, list[TaskResult]], topic: str) -> list[TaskResult]:
        """Case-insensitive lookup of a topic's results in a grouped dict."""
        normalized = topic.strip().lower()
        for key, results in grouped.items():
            if key.lower() == normalized:
                return results
        return []

    async def _generate_introduction(
        self,
        topics: list[str],
        enhanced_prompt: EnhancedPrompt,
    ) -> str:
        """Generate report introduction using LLM."""
        system_prompt = "You are an expert research report writer. Write a professional 150-word introduction for a research report."

        topics_text = ", ".join(topics)
        user_message = f"""Write an introduction for a research report on: {topics_text}

The research covers: {', '.join(enhanced_prompt.required_sections)}

Make it engaging, clear, and approximately 150 words."""

        try:
            introduction = await self.llm.call_llm(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.7,
            )
            return introduction.strip()
        except Exception as e:
            logger.warning(f"Failed to generate introduction: {str(e)}")
            return f"This report explores {topics_text} in detail, covering {', '.join(enhanced_prompt.required_sections).lower()}."

    async def _generate_conclusion(
        self,
        topics: list[str],
        findings_summary: str,
    ) -> str:
        """Generate report conclusion using LLM."""
        system_prompt = "You are an expert research report writer. Write a professional 150-word conclusion for a research report."

        topics_text = ", ".join(topics)
        user_message = f"""Write a conclusion for a research report on: {topics_text}

Key findings:
{findings_summary}

Make it comprehensive and approximately 150 words."""

        try:
            conclusion = await self.llm.call_llm(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.7,
            )
            return conclusion.strip()
        except Exception as e:
            logger.warning(f"Failed to generate conclusion: {str(e)}")
            return "This research demonstrates the importance and relevance of these topics in today's landscape."

    async def _generate_comparative_analysis(
        self,
        topics: list[str],
        grouped_results: dict[str, list[TaskResult]],
    ) -> str:
        """Generate comparative analysis between topics."""
        if len(topics) < 2:
            return ""

        system_prompt = "You are an expert researcher. Write a comparative analysis between research topics."

        topics_list = []
        for topic in topics:
            findings = " ".join([r.findings for r in self._results_for_topic(grouped_results, topic)])
            topics_list.append(f"{topic}: {findings[:500]}")

        user_message = f"""Compare and contrast the following:

{chr(10).join(topics_list)}

Write a 300-word comparative analysis highlighting similarities, differences, and implications."""

        try:
            analysis = await self.llm.call_llm(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.7,
            )
            return analysis.strip()
        except Exception as e:
            logger.warning(f"Failed to generate comparative analysis: {str(e)}")
            return ""

    def _format_section_text(self, topic: str, results: list[TaskResult]) -> str:
        """Format findings for a topic into readable text."""
        text = f"\n### {topic}\n\n"

        # Group by subtopic
        by_subtopic = {}
        for result in results:
            if result.subtopic not in by_subtopic:
                by_subtopic[result.subtopic] = result
            else:
                # Keep the completed one
                if result.status == "completed":
                    by_subtopic[result.subtopic] = result

        for subtopic in sorted(by_subtopic.keys()):
            result = by_subtopic[subtopic]
            text += f"#### {result.subtopic.replace('_', ' ').title()}\n\n"
            text += result.findings + "\n\n"

        return text

    def _extract_all_sources(self, results: list[TaskResult]) -> list[ResearchSource]:
        """Extract and deduplicate all sources from results."""
        seen_urls = set()
        sources = []

        for result in results:
            for source in result.sources:
                if source.url and source.url not in seen_urls:
                    seen_urls.add(source.url)
                    sources.append(source)

        return sources

    async def format_report(
        self,
        task_results: list[TaskResult],
        enhanced_prompt: EnhancedPrompt,
    ) -> ResearchReport:
        """
        Format task results into a professional research report.

        Args:
            task_results: Results from executed tasks
            enhanced_prompt: Original enhanced prompt

        Returns:
            Formatted research report
        """
        logger.info(f"Formatting report for {len(enhanced_prompt.topics)} topics")

        try:
            # Group results by topic
            grouped = self._group_results_by_topic(task_results)

            # Generate introduction
            logger.debug("Generating introduction...")
            introduction = await self._generate_introduction(
                enhanced_prompt.topics,
                enhanced_prompt,
            )

            # Format sections for each topic
            logger.debug("Formatting sections...")
            sections = {}
            for topic in enhanced_prompt.topics:
                topic_results = self._results_for_topic(grouped, topic)
                if topic_results:
                    sections[topic] = self._format_section_text(topic, topic_results)
                else:
                    sections[topic] = f"\n### {topic}\n\nNo results found for this topic.\n"

            # Generate comparative analysis if needed
            comparative_analysis = ""
            if enhanced_prompt.compare_topics and len(enhanced_prompt.topics) > 1:
                logger.debug("Generating comparative analysis...")
                comparative_analysis = await self._generate_comparative_analysis(
                    enhanced_prompt.topics,
                    grouped,
                )

            # Generate conclusion
            findings_summary = "\n".join([s[:200] for s in sections.values()])
            logger.debug("Generating conclusion...")
            conclusion = await self._generate_conclusion(
                enhanced_prompt.topics,
                findings_summary,
            )

            # Extract all sources
            all_sources = self._extract_all_sources(task_results)

            # Calculate total words
            total_text = introduction + "\n" + "\n".join(sections.values()) + "\n" + conclusion
            total_words = len(total_text.split())

            # Create report object
            report = ResearchReport(
                title=f"Research Report: {', '.join(enhanced_prompt.topics)}",
                topics=enhanced_prompt.topics,
                introduction=introduction,
                sections=sections,
                comparative_analysis=comparative_analysis,
                conclusion=conclusion,
                citations=all_sources,
                total_words=total_words,
            )

            logger.info(f"Report formatted: {total_words} words, {len(all_sources)} sources")
            return report

        except Exception as e:
            logger.error(f"Error formatting report: {str(e)}")
            raise

    def report_to_text(self, report: ResearchReport) -> str:
        """Convert report to plain text format."""
        text = f"# {report.title}\n\n"

        text += "## Introduction\n\n"
        text += report.introduction + "\n\n"

        for section in report.sections.values():
            text += section + "\n"

        if report.comparative_analysis:
            text += "\n## Comparative Analysis\n\n"
            text += report.comparative_analysis + "\n\n"

        text += "\n## Conclusion\n\n"
        text += report.conclusion + "\n\n"

        if report.citations:
            text += "\n## Sources\n\n"
            for idx, source in enumerate(report.citations, 1):
                text += f"{idx}. {source.title}\n"
                text += f"   URL: {source.url}\n\n"

        text += f"\n---\n\nReport generated: {report.generated_at}\n"
        text += f"Total words: {report.total_words}\n"

        return text

    def report_to_markdown(self, report: ResearchReport) -> str:
        """Convert report to markdown format."""
        md = f"# {report.title}\n\n"

        md += "## Introduction\n\n"
        md += report.introduction + "\n\n"

        for section in report.sections.values():
            md += section + "\n"

        if report.comparative_analysis:
            md += "\n## Comparative Analysis\n\n"
            md += report.comparative_analysis + "\n\n"

        md += "\n## Conclusion\n\n"
        md += report.conclusion + "\n\n"

        if report.citations:
            md += "\n## Sources\n\n"
            for idx, source in enumerate(report.citations, 1):
                md += f"{idx}. [{source.title}]({source.url})\n"

        md += f"\n---\n\n_Report generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}_\n"
        md += f"_Total words: {report.total_words}_\n"

        return md


# Singleton instance
_formatter_agent = None


def get_formatter() -> FormatterAgent:
    """Get formatter agent singleton."""
    global _formatter_agent
    if _formatter_agent is None:
        _formatter_agent = FormatterAgent()
        logger.info("Formatter agent initialized")
    return _formatter_agent
