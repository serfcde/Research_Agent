"""File writer tool for exporting research reports."""

from datetime import datetime
from pathlib import Path

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FileWriter:
    """Tool for writing research reports to files."""

    def __init__(self, output_dir: Path | None = None):
        """
        Initialize file writer.

        Args:
            output_dir: Output directory (uses settings default if None)
        """
        self.output_dir = output_dir or settings.get_research_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_filename(self, topic: str, file_format: str = "txt") -> str:
        """
        Generate filename for report.

        Args:
            topic: Research topic (used in filename)
            file_format: File format (txt, md, etc.)

        Returns:
            Formatted filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize topic for filename
        safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)
        safe_topic = safe_topic.replace(" ", "_")[:50]
        return f"research_{safe_topic}_{timestamp}.{file_format}"

    def save_report_txt(self, content: str, topic: str = "research") -> Path:
        """
        Save report to TXT file.

        Args:
            content: Report content
            topic: Topic name for filename

        Returns:
            Path to saved file
        """
        try:
            filename = self._get_filename(topic, "txt")
            file_path = self.output_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                # Add header
                f.write("=" * 80 + "\n")
                f.write("RESEARCH REPORT\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Topic: {topic}\n")
                f.write("=" * 80 + "\n\n")

                # Write content
                f.write(content)

                # Add footer
                f.write("\n\n" + "=" * 80 + "\n")
                f.write(f"Report saved to: {file_path}\n")
                f.write(f"Total words: {len(content.split())}\n")
                f.write("=" * 80 + "\n")

            logger.info(f"Report saved to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save report: {str(e)}")
            raise

    def save_report_md(self, content: str, topic: str = "research") -> Path:
        """
        Save report to Markdown file.

        Args:
            content: Report content (markdown format)
            topic: Topic name for filename

        Returns:
            Path to saved file
        """
        try:
            filename = self._get_filename(topic, "md")
            file_path = self.output_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# Research Report\n\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Topic:** {topic}\n\n")
                f.write("---\n\n")
                f.write(content)

            logger.info(f"Report saved to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save report: {str(e)}")
            raise

    def save_report_json(self, content: dict, topic: str = "research") -> Path:
        """
        Save report to JSON file.

        Args:
            content: Report content (dict)
            topic: Topic name for filename

        Returns:
            Path to saved file
        """
        import json

        try:
            filename = self._get_filename(topic, "json")
            file_path = self.output_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, default=str)

            logger.info(f"Report saved to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save report: {str(e)}")
            raise


# Singleton instance
_file_writer: FileWriter | None = None


def get_file_writer(output_dir: Path | None = None) -> FileWriter:
    """Get file writer singleton."""
    global _file_writer
    if _file_writer is None:
        _file_writer = FileWriter(output_dir)
        logger.info("File writer initialized")
    return _file_writer


async def save_research_report(content: str, topic: str = "research", format: str = "txt") -> Path:
    """
    Convenience function for saving research report.

    Args:
        content: Report content
        topic: Topic name
        format: Format (txt, md, json)

    Returns:
        Path to saved file
    """
    writer = get_file_writer()

    if format == "md":
        return writer.save_report_md(content, topic)
    elif format == "json":
        return writer.save_report_json(content, topic)
    else:
        return writer.save_report_txt(content, topic)
