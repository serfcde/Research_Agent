"""LLM service with Groq support — routed through Pipelock firewall proxy."""

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

# Pipelock forward proxy address (change port if you configured a different one)
PIPELOCK_PROXY = "http://127.0.0.1:8888"


class LLMService:
    """Service for interacting with Groq LLM via Pipelock firewall."""

    def __init__(self):
        # ✅ Route all Groq API calls through Pipelock proxy for monitoring
        http_client = httpx.AsyncClient(
            proxy=PIPELOCK_PROXY,
            verify=False,  # Pipelock terminates TLS locally; disable cert check for proxy
        )
        self.client = AsyncGroq(
            api_key=settings.groq_api_key,
            http_client=http_client,
        )
        self.model = "llama-3.3-70b-versatile"
        self.timeout = settings.llm_timeout_seconds
        self.max_tokens = settings.llm_max_tokens
        logger.info("LLM service initialized with Pipelock proxy")

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
            logger.info(f"Calling LLM [{self.model}] via Pipelock proxy")

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

    async def count_tokens(self, text: str) -> int:
        return len(text) // 4


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service