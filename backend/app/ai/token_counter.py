"""Token counting utilities using tiktoken."""
try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore

from ..core.tracing import get_logger

logger = get_logger(__name__)


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Count tokens in text using tiktoken.
    
    Falls back to character-based estimation if tiktoken is not available.
    
    Args:
        text: Text to count tokens for
        model: Model name for encoding
        
    Returns:
        Token count
    """
    if tiktoken is None:
        # Fallback: rough estimate of 4 chars per token
        logger.warning("tiktoken not available, using character-based estimation")
        return len(text) // 4

    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Failed to count tokens with tiktoken: {e}, using estimation")
        return len(text) // 4


def check_token_budget(text: str, max_tokens: int, model: str = "gpt-4o") -> tuple[bool, int]:
    """
    Check if text fits within token budget.
    
    Args:
        text: Text to check
        max_tokens: Maximum allowed tokens
        model: Model name for encoding
        
    Returns:
        Tuple of (fits_budget, actual_token_count)
    """
    token_count = count_tokens(text, model)
    return token_count <= max_tokens, token_count


def truncate_to_token_limit(text: str, max_tokens: int, model: str = "gpt-4o") -> str:
    """
    Truncate text to fit within token limit.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum allowed tokens
        model: Model name for encoding
        
    Returns:
        Truncated text
    """
    if tiktoken is None:
        # Fallback: character-based truncation
        max_chars = max_tokens * 4
        return text[:max_chars]

    try:
        encoding = tiktoken.encoding_for_model(model)
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)
    except Exception as e:
        logger.warning(f"Failed to truncate with tiktoken: {e}, using character-based")
        max_chars = max_tokens * 4
        return text[:max_chars]

# Made with Bob
