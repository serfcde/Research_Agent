"""LLM service for OpenAI integration."""

import json
import asyncio
from typing import Any, Optional, Dict
from openai import AsyncOpenAI, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """Service for interacting with OpenAI LLM."""

    def __init__(self):
        """Initialize LLM service with OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.timeout = settings.llm_timeout_seconds
        self.max_tokens = settings.llm_max_tokens

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
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
        """
        Call OpenAI LLM with retry logic.

        Args:
            system_prompt: System role prompt
            user_prompt: User message
            response_format: JSON schema for structured output (optional)
            temperature: Creativity temperature (0-2)

        Returns:
            LLM response text or JSON string
        """
        try:
            logger.info(f"Calling LLM with model {self.model}")

            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "timeout": self.timeout,
            }

            # Add response format if provided (for JSON mode)
            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)

            result = response.choices[0].message.content
            logger.info(f"LLM response received ({len(result)} chars)")

            return result

        except (RateLimitError, APIError) as e:
            logger.error(f"LLM API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected LLM error: {str(e)}")
            raise

    async def call_llm_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Call LLM requesting JSON response.

        Args:
            system_prompt: System role prompt
            user_prompt: User message
            temperature: Creativity temperature

        Returns:
            Parsed JSON response
        """
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
            logger.debug(f"Response was: {response_text}")
            raise

    async def summarize_content(
        self,
        content: str,
        max_words: int = 300,
    ) -> str:
        """
        Summarize content using LLM.

        Args:
            content: Content to summarize
            max_words: Maximum words in summary

        Returns:
            Summarized content
        """
        system_prompt = f"You are an expert researcher. Summarize the following content in approximately {max_words} words. Focus on key facts, statistics, and insights."

        user_prompt = f"Content to summarize:\n\n{content}"

        return await self.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
        )

    async def count_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation).

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters
        return len(text) // 4


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
        logger.info("LLM service initialized")
    return _llm_service
