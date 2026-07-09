"""Application configuration management."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Research Agent"
    app_version: str = "1.0.0"
    debug: bool = Field(default=True, validation_alias="APP_DEBUG")
    log_level: str = "INFO"

    # LLM Configuration (Groq)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: int = 60
    llm_max_tokens: int = 4000

    # Pipelock LLM-traffic proxy (optional local dev tooling)
    pipelock_proxy_url: str = ""
    pipelock_proxy_insecure: bool = False

    # Tavily API Configuration
    tavily_api_key: str = ""
    tavily_max_concurrent_searches: int = 5
    tavily_search_timeout_seconds: int = 30
    tavily_max_retries: int = 2

    # SerpAPI Configuration (search fallback)
    serpapi_api_key: str = ""

    # Persistence (Postgres: runs + LangGraph checkpoints). Empty = in-memory.
    database_url: str = ""

    # API security. Comma-separated X-API-Key values; empty = auth disabled.
    api_keys: str = ""
    cors_origins: str = "http://localhost:3000"

    # Research Configuration
    research_output_dir: str = "./research_outputs"
    research_timeout_minutes: int = 10

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_research_output_dir(self) -> Path:
        """Get or create research output directory."""
        output_dir = Path(self.research_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


# Singleton instance
settings = get_settings()
