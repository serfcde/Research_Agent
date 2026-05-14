"""Web search tool integration with Tavily and fallback to SerpAPI.
All outbound HTTP traffic is routed through the Pipelock firewall proxy.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
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

# Pipelock forward proxy — all search traffic is inspected here
PIPELOCK_PROXY = "http://127.0.0.1:8888"


def _proxied_client(timeout: int) -> httpx.AsyncClient:
    """Return an httpx client that routes through the Pipelock proxy."""
    return httpx.AsyncClient(
        proxy=PIPELOCK_PROXY,
        verify=False,   # Pipelock terminates TLS locally
        timeout=timeout,
    )


class WebSearchClient:
    """Client for performing web searches via Pipelock firewall proxy."""

    def __init__(self):
        self.tavily_api_key = settings.tavily_api_key
        self.serpapi_api_key = settings.serpapi_api_key
        self.timeout = settings.tavily_search_timeout_seconds
        self.max_retries = settings.tavily_max_retries
        self.tavily_base_url = "https://api.tavily.com"
        self.serpapi_base_url = "https://serpapi.com/search.json"
        logger.info("Web search client initialized with Pipelock proxy")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Web search error, retrying... (attempt {retry_state.attempt_number})"
        ),
    )
    async def tavily_search(self, query: str) -> Dict[str, Any]:
        """Search using Tavily API, routed through Pipelock."""
        logger.info(f"Tavily search via Pipelock: {query[:60]}...")

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "max_results": 5,
            "include_images": False,
        }

        try:
            # ✅ Use proxied client — traffic visible in Pipelock dashboard
            async with _proxied_client(self.timeout) as client:
                response = await client.post(
                    f"{self.tavily_base_url}/search",
                    json=payload,
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
        """Search using SerpAPI (fallback), routed through Pipelock."""
        logger.info(f"SerpAPI search via Pipelock (fallback): {query[:60]}...")

        params = {
            "q": query,
            "api_key": self.serpapi_api_key,
            "engine": "google",
            "num": 5,
        }

        try:
            # ✅ Use proxied client
            async with _proxied_client(self.timeout) as client:
                response = await client.get(
                    self.serpapi_base_url,
                    params=params,
                    follow_redirects=True,
                )
                response.raise_for_status()
                result = response.json()
                logger.info("SerpAPI returned results")
                return result

        except httpx.HTTPError as e:
            logger.error(f"SerpAPI search failed: {str(e)}")
            raise

    def _parse_tavily_results(self, tavily_response: Dict[str, Any]) -> List[ResearchSource]:
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
        try:
            result = await self.tavily_search(query)
            sources = self._parse_tavily_results(result)
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


_search_client: Optional[WebSearchClient] = None


def get_search_client() -> WebSearchClient:
    global _search_client
    if _search_client is None:
        _search_client = WebSearchClient()
    return _search_client


async def search_web(query: str) -> tuple[str, List[ResearchSource]]:
    client = get_search_client()
    return await client.search(query)