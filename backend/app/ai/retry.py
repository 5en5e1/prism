"""Retry policy for AI calls."""
import asyncio
import random
from typing import Any, Callable, TypeVar

from openai import APIError, RateLimitError as OpenAIRateLimitError, APITimeoutError

from ..core.exceptions import ContentFilterError, RateLimitError, TimeoutError
from ..core.tracing import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    **kwargs: Any,
) -> T:
    """
    Execute a function with exponential backoff retry.
    
    Retries on:
    - Rate limit errors
    - Timeout errors
    - Transient network errors
    
    Does not retry on:
    - Content filter errors
    - Validation errors
    - Malformed response errors
    
    Args:
        func: Async function to execute
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        **kwargs: Keyword arguments for func
        
    Returns:
        Result from func
        
    Raises:
        RateLimitError: If rate limited after all retries
        TimeoutError: If timed out after all retries
        ContentFilterError: If content was filtered
        Other exceptions: If non-retryable error occurs
    """
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)

        except OpenAIRateLimitError as e:
            last_exception = RateLimitError(str(e))
            if attempt < max_attempts - 1:
                delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
                logger.warning(
                    f"Rate limited, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Rate limited after {max_attempts} attempts")
                raise last_exception

        except APITimeoutError as e:
            last_exception = TimeoutError(str(e))
            if attempt < max_attempts - 1:
                delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
                logger.warning(
                    f"Request timed out, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Timed out after {max_attempts} attempts")
                raise last_exception

        except APIError as e:
            # Check if it's a content filter error
            error_message = str(e).lower()
            if "content_filter" in error_message or "content policy" in error_message:
                logger.error("Content filtered by OpenAI")
                raise ContentFilterError(str(e))

            # For other API errors, retry if transient
            if attempt < max_attempts - 1 and e.status_code in [500, 502, 503, 504]:
                delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
                logger.warning(
                    f"Transient API error ({e.status_code}), retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)
            else:
                # Non-retryable API error
                raise

        except Exception as e:
            # Non-retryable error
            logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
            raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic failed unexpectedly")

# Made with Bob
