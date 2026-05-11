"""Web search tool integration with Tavily and fallback to SerpAPI."""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.config.settings import settings
from app.utils.logger import get_logger
from app.models.schemas import ResearchSource

logger = get_logger(__name__)


class WebSearchClient:
    """Client for performing web searches."""

    def __init__(self):
        """Initialize web search client."""
        self.tavily_api_key = settings.tavily_api_key
        self.serpapi_api_key = settings.serpapi_api_key
        self.timeout = settings.tavily_search_timeout_seconds
        self.max_retries = settings.tavily_max_retries
        self.tavily_base_url = "https://api.tavily.com"
        self.serpapi_base_url = "https://serpapi.com"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Web search error, retrying... (attempt {retry_state.attempt_number})"
        ),
    )
    async def tavily_search(self, query: str) -> Dict[str, Any]:
        """
        Search using Tavily API (AI-optimized).

        Args:
            query: Search query

        Returns:
            Search results dictionary
        """
        logger.info(f"Tavily search: {query[:60]}...")

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "max_results": 5,
            "include_images": False,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.tavily_base_url}/search",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                result = response.json()

                logger.info(f"Tavily returned {len(result.get('results', []))} results")
                return result

        except httpx.HTTPError as e:
            logger.error(f"Tavily search failed: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"SerpAPI error, retrying... (attempt {retry_state.attempt_number})"
        ),
    )
    async def serpapi_search(self, query: str) -> Dict[str, Any]:
        """
        Search using SerpAPI (fallback).

        Args:
            query: Search query

        Returns:
            Search results dictionary
        """
        logger.info(f"SerpAPI search (fallback): {query[:60]}...")

        params = {
            "q": query,
            "api_key": self.serpapi_api_key,
            "engine": "google",
            "num": 5,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.serpapi_base_url,
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                result = response.json()

                logger.info(f"SerpAPI returned results")
                return result

        except httpx.HTTPError as e:
            logger.error(f"SerpAPI search failed: {str(e)}")
            raise

    def _parse_tavily_results(self, tavily_response: Dict[str, Any]) -> List[ResearchSource]:
        """Parse Tavily API response into ResearchSource objects."""
        sources = []
        for result in tavily_response.get("results", []):
            source = ResearchSource(
                title=result.get("title", "Unknown"),
                url=result.get("url", ""),
                snippet=result.get("content", result.get("snippet", "No content"))[:300],
            )
            sources.append(source)
        return sources

    def _parse_serpapi_results(self, serpapi_response: Dict[str, Any]) -> List[ResearchSource]:
        """Parse SerpAPI response into ResearchSource objects."""
        sources = []
        for result in serpapi_response.get("organic_results", [])[:5]:
            source = ResearchSource(
                title=result.get("title", "Unknown"),
                url=result.get("link", ""),
                snippet=result.get("snippet", "")[:300],
            )
            sources.append(source)
        return sources

    async def search(self, query: str, use_fallback: bool = True) -> tuple[str, List[ResearchSource]]:
        """
        Perform web search with fallback logic.

        Args:
            query: Search query
            use_fallback: Whether to fallback to SerpAPI on Tavily failure

        Returns:
            Tuple of (combined_content, sources)
        """
        try:
            result = await self.tavily_search(query)
            sources = self._parse_tavily_results(result)

            # Combine content from all results
            content = " ".join([s.snippet for s in sources])
            return content, sources

        except Exception as e:
            logger.warning(f"Tavily search failed: {str(e)}")

            if use_fallback and self.serpapi_api_key:
                try:
                    result = await self.serpapi_search(query)
                    sources = self._parse_serpapi_results(result)
                    content = " ".join([s.snippet for s in sources])
                    return content, sources
                except Exception as fallback_error:
                    logger.error(f"SerpAPI fallback also failed: {str(fallback_error)}")
                    return "", []

            raise


# Singleton instance
_search_client: Optional[WebSearchClient] = None


def get_search_client() -> WebSearchClient:
    """Get web search client singleton."""
    global _search_client
    if _search_client is None:
        _search_client = WebSearchClient()
        logger.info("Web search client initialized")
    return _search_client


async def search_web(query: str) -> tuple[str, List[ResearchSource]]:
    """
    Convenience function for web search.

    Args:
        query: Search query

    Returns:
        Tuple of (content, sources)
    """
    client = get_search_client()
    return await client.search(query)
