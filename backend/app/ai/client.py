"""Async OpenAI client wrapper."""
from typing import Any

from openai import AsyncOpenAI

from ..ai.retry import with_retry
from ..config import settings
from ..core.exceptions import MalformedResponseError
from ..core.tracing import get_logger

logger = get_logger(__name__)


class AIClient:
    """Wrapper around OpenAI async client with retry logic."""

    def __init__(self):
        """Initialize the OpenAI client."""
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_s,
            # with_retry() is the single retry authority. The SDK's default
            # max_retries=2 would nest inside each app-level attempt, turning
            # one timeout into minutes of silent retrying.
            max_retries=0,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_completion_tokens: int | None = None,
        response_format: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """
        Call OpenAI chat completion with retry logic.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (defaults to config)
            temperature: Sampling temperature
            max_completion_tokens: Maximum tokens to generate (GPT-5 parameter)
            response_format: Response format ("json_schema" for structured output)
            reasoning_effort: Effort for reasoning models, e.g. "minimal"
                (applied only to gpt-5*/o-series; ignored otherwise)

        Returns:
            OpenAI API response dict
        """
        model = model or settings.openai_default_model

        # Embed model + reasoning_effort in the message: the JSON log
        # formatter only renders %(message)s and drops `extra` fields.
        logger.info(
            f"Calling OpenAI API (model={model}, "
            f"reasoning_effort={reasoning_effort}, "
            f"max_completion_tokens={max_completion_tokens})",
            extra={
                "model": model,
                "temperature": temperature,
                "max_completion_tokens": max_completion_tokens,
                "reasoning_effort": reasoning_effort,
                "message_count": len(messages),
            },
        )

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # GPT-5 and reasoning (o-series) models only support the default
        # temperature; sending a custom value returns a 400 error.
        is_reasoning_model = model.startswith(("gpt-5", "o1", "o3", "o4"))
        if not is_reasoning_model:
            kwargs["temperature"] = temperature

        # reasoning_effort is only valid on reasoning models; non-reasoning
        # models 400 on it.
        if is_reasoning_model and reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        if max_completion_tokens:
            kwargs["max_completion_tokens"] = max_completion_tokens

        if response_format == "json_schema":
            kwargs["response_format"] = {"type": "json_object"}

        # Call with retry
        response = await with_retry(
            self.client.chat.completions.create,
            **kwargs,
        )

        # Convert to dict for easier handling
        result: dict[str, Any] = response.model_dump()

        # Guard against empty / truncated completions. Reasoning models
        # (gpt-5*, o1/o3/o4) spend max_completion_tokens on reasoning before
        # any visible output, so an undersized budget yields a 200 OK with
        # finish_reason="length" and empty content. Surfacing this here gives
        # an actionable error instead of a cryptic JSON parse failure
        # ("Expecting value: line 1 column 1 (char 0)") in the handler.
        choice = (result.get("choices") or [{}])[0]
        finish_reason = choice.get("finish_reason")
        content = (choice.get("message") or {}).get("content") or ""

        if not content.strip():
            usage = result.get("usage") or {}
            if finish_reason == "length":
                raise MalformedResponseError(
                    "Model returned empty content with finish_reason='length'. "
                    f"The max_completion_tokens budget ({max_completion_tokens}) "
                    "was exhausted before any visible output was produced "
                    f"(completion_tokens={usage.get('completion_tokens')}, "
                    "likely consumed by reasoning). Increase "
                    "OPENAI_MAX_COMPLETION_TOKENS or use a non-reasoning model."
                )
            raise MalformedResponseError(
                f"Model returned empty content (finish_reason={finish_reason!r})."
            )

        if finish_reason == "length":
            logger.warning(
                "Completion truncated by token limit; output is likely invalid",
                extra={
                    "model": model,
                    "max_completion_tokens": max_completion_tokens,
                },
            )

        return result

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.close()

# Made with Bob
