"""Async OpenAI client wrapper."""
from typing import Any

from openai import AsyncOpenAI

from ..ai.retry import with_retry
from ..config import settings
from ..core.tracing import get_logger

logger = get_logger(__name__)


class AIClient:
    """Wrapper around OpenAI async client with retry logic."""

    def __init__(self):
        """Initialize the OpenAI client."""
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_s,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        """
        Call OpenAI chat completion with retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (defaults to config)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Response format ("json_schema" for structured output)
            
        Returns:
            OpenAI API response dict
        """
        model = model or settings.openai_default_model

        logger.info(
            f"Calling OpenAI API",
            extra={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "message_count": len(messages),
            },
        )

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        if response_format == "json_schema":
            kwargs["response_format"] = {"type": "json_object"}

        # Call with retry
        response = await with_retry(
            self.client.chat.completions.create,
            **kwargs,
        )

        # Convert to dict for easier handling
        return response.model_dump()

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.close()

# Made with Bob
