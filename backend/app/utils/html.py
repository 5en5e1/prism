"""HTML utility functions."""
from bs4 import BeautifulSoup


def extract_text(html: str) -> str:
    """
    Extract plain text from HTML.
    
    Args:
        html: HTML content
        
    Returns:
        Plain text content
    """
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator=" ", strip=True)


def count_elements(html: str) -> int:
    """
    Count the number of elements in HTML.
    
    Args:
        html: HTML content
        
    Returns:
        Number of elements
    """
    soup = BeautifulSoup(html, "lxml")
    return len(list(soup.find_all(True)))


def validate_html(html: str) -> bool:
    """
    Check if HTML is valid and parseable.
    
    Args:
        html: HTML content
        
    Returns:
        True if valid, False otherwise
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        return soup is not None
    except Exception:
        return False

# Made with Bob
