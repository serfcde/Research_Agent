"""LLM service backed by Groq, with optional Pipelock proxy routing."""

import contextvars
import json
import httpx
from typing import Any, Optional, Dict
from groq import AsyncGroq
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Per-run token accounting. The orchestrator seeds this contextvar at the
# start of a pipeline; every LLM call inside that task tree (including
# asyncio.gather children, which inherit the context) accumulates the real
# usage numbers reported by the Groq API.
_usage_ctx: contextvars.ContextVar[Optional[Dict[str, int]]] = contextvars.ContextVar(
    "llm_usage", default=None
)


def start_usage_tracking() -> Dict[str, int]:
    """Seed token accounting for the current task tree and return the dict."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "llm_calls": 0}
    _usage_ctx.set(usage)
    return usage


def _record_usage(response) -> None:
    usage = _usage_ctx.get()
    if usage is None or getattr(response, "usage", None) is None:
        return
    usage["prompt_tokens"] += response.usage.prompt_tokens or 0
    usage["completion_tokens"] += response.usage.completion_tokens or 0
    usage["total_tokens"] += response.usage.total_tokens or 0
    usage["llm_calls"] += 1


class LLMService:
    """Service for interacting with the Groq LLM."""

    def __init__(self):
        client_kwargs: Dict[str, Any] = {"api_key": settings.groq_api_key}

        if settings.pipelock_proxy_url:
            # Route Groq traffic through the Pipelock forward proxy for
            # monitoring. Cert verification stays on unless explicitly
            # disabled for a local TLS-terminating proxy.
            client_kwargs["http_client"] = httpx.AsyncClient(
                proxy=settings.pipelock_proxy_url,
                verify=not settings.pipelock_proxy_insecure,
            )
            logger.info(f"LLM traffic routed via Pipelock proxy: {settings.pipelock_proxy_url}")

        self.client = AsyncGroq(**client_kwargs)
        self.model = settings.groq_model
        self.timeout = settings.llm_timeout_seconds
        self.max_tokens = settings.llm_max_tokens
        logger.info(f"LLM service initialized (model={self.model})")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM API error, retrying... (attempt {retry_state.attempt_number})"
        ),
    )
    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
    ) -> str:
        try:
            logger.info(f"Calling LLM [{self.model}]")

            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": self.max_tokens,
            }

            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)
            _record_usage(response)
            result = response.choices[0].message.content
            logger.info(f"LLM response received ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"LLM API error: {str(e)}")
            raise

    async def call_llm_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        response_format = {"type": "json_object"}
        response_text = await self.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=response_format,
            temperature=temperature,
        )
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {str(e)}")
            raise

    async def summarize_content(self, content: str, max_words: int = 300) -> str:
        system_prompt = (
            f"You are an expert researcher. Summarize the following content in "
            f"approximately {max_words} words. Focus on key facts, statistics, and insights."
        )
        return await self.call_llm(
            system_prompt=system_prompt,
            user_prompt=f"Content to summarize:\n\n{content}",
            temperature=0.5,
        )

_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service