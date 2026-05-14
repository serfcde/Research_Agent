"""Formatter Agent - Create professional research reports."""

import re
from typing import List, Dict
from datetime import datetime
from app.services.llm_service import get_llm_service
from app.models.schemas import (
    TaskResult,
    EnhancedPrompt,
    ResearchReport,
    ResearchSource,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FormatterAgent:
    """Agent for formatting research results into professional reports."""

    def __init__(self):
        """Initialize formatter agent."""
        self.llm = get_llm_service()

    def _group_results_by_topic(self, results: List[TaskResult]) -> Dict[str, List[TaskResult]]:
        """Group task results by topic, case-insensitive."""
        grouped = {}
        for result in results:
            # Normalize key to lowercase for grouping
            key = result.topic.strip().lower()
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)
        return grouped

    async def _generate_introduction(
        self,
        topics: List[str],
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
        topics: List[str],
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
        topics: List[str],
        grouped_results: Dict[str, List[TaskResult]],
    ) -> str:
        """Generate comparative analysis between topics."""
        if len(topics) < 2:
            return ""

        system_prompt = "You are an expert researcher. Write a comparative analysis between research topics."

        topics_list = []
        for topic in topics:
            findings = " ".join([r.findings for r in grouped_results.get(topic.strip().lower(), [])])
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

    def _format_section_text(self, topic: str, results: List[TaskResult]) -> str:
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

    def _extract_all_sources(self, results: List[TaskResult]) -> List[ResearchSource]:
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
        task_results: List[TaskResult],
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
                # ✅ normalize lookup key
                topic_key = topic.strip().lower()
                topic_results = grouped.get(topic_key, [])
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

        for topic, section in report.sections.items():
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

        for topic, section in report.sections.items():
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
