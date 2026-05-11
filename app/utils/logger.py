"""Structured logging configuration."""

import sys
from loguru import logger as _logger
from app.config.settings import settings

# Remove default handler
_logger.remove()

# Add custom handler with formatting
_logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# Add file handler for errors
_logger.add(
    "logs/error.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="10 MB",
    retention="1 week",
)

# Add file handler for all logs
_logger.add(
    "logs/debug.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=settings.log_level,
    rotation="50 MB",
    retention="2 weeks",
)

logger = _logger


def get_logger(name: str):
    """Get a logger instance with a specific name."""
    return logger.bind(name=name)
