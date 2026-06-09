"""HTML chunking strategies for large documents."""
from typing import Any

from bs4 import BeautifulSoup, Tag


def chunk_by_sections(html: str, max_chunks: int = 10) -> list[dict[str, Any]]:
    """
    Chunk HTML by top-level sections.
    
    Useful for two-pass processing where we first identify relevant sections,
    then expand them in a second pass.
    
    Args:
        html: HTML content to chunk
        max_chunks: Maximum number of chunks to create
        
    Returns:
        List of chunk dictionaries with 'id', 'tag', 'html' keys
    """
    soup = BeautifulSoup(html, "lxml")
    chunks: list[dict[str, Any]] = []

    # Find body or use root
    body = soup.find("body")
    if not body or not isinstance(body, Tag):
        body = soup

    # Get top-level children
    children = [child for child in body.children if isinstance(child, Tag)]

    # Chunk by sections or divs
    for i, child in enumerate(children[:max_chunks]):
        chunk_id = f"chunk_{i}"
        chunks.append(
            {
                "id": chunk_id,
                "tag": child.name,
                "html": str(child),
                "element_count": len(list(child.descendants)),
            }
        )

    return chunks


def estimate_token_count(text: str) -> int:
    """
    Rough estimate of token count.
    
    More accurate counting should use tiktoken, but this is fast for
    quick checks.
    
    Args:
        text: Text to estimate
        
    Returns:
        Estimated token count
    """
    # Rough heuristic: ~4 characters per token
    return len(text) // 4


def should_chunk(html: str, max_tokens: int = 100_000) -> bool:
    """
    Determine if HTML should be chunked based on size.
    
    Args:
        html: HTML content
        max_tokens: Maximum tokens before chunking
        
    Returns:
        True if chunking is recommended
    """
    estimated_tokens = estimate_token_count(html)
    return estimated_tokens > max_tokens
