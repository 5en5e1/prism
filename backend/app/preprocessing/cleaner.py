"""HTML cleaning utilities."""
import re
from typing import Any

from bs4 import BeautifulSoup, Comment, Tag

from ..core.exceptions import HTMLParseError


def clean_html(html: str, preserve_hidden: bool = False) -> str:
    """
    Clean HTML by removing scripts, comments, base64 images, and noise.
    
    Args:
        html: Raw HTML content
        preserve_hidden: If True, keep hidden elements (useful for QA)
        
    Returns:
        Cleaned HTML string
        
    Raises:
        HTMLParseError: If HTML cannot be parsed
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        raise HTMLParseError(f"Failed to parse HTML: {e}")

    # Remove script and style content but keep tags as markers
    for tag in soup.find_all(["script", "style"]):
        tag.string = ""

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Strip data: URI images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:"):
            img["src"] = ""
            img["data-stripped"] = "image"

    # Remove excessive aria-* attributes (keep only aria-label)
    for tag in soup.find_all(True):
        if isinstance(tag, Tag):
            attrs_to_remove = [
                attr for attr in tag.attrs if attr.startswith("aria-") and attr != "aria-label"
            ]
            for attr in attrs_to_remove:
                del tag[attr]

    # Remove hidden elements unless preserve_hidden is True
    if not preserve_hidden:
        for tag in soup.find_all(True):
            if isinstance(tag, Tag):
                # Check for display:none in style
                style = tag.get("style", "")
                if "display:none" in style.replace(" ", "").lower():
                    tag.decompose()
                    continue

                # Check for hidden attribute
                if tag.get("hidden") is not None:
                    tag.decompose()
                    continue

                # Check for aria-hidden="true"
                if tag.get("aria-hidden") == "true":
                    tag.decompose()
                    continue

    # Collapse whitespace
    html_str = str(soup)
    html_str = re.sub(r"\s+", " ", html_str)
    html_str = re.sub(r">\s+<", "><", html_str)

    return html_str.strip()


def minimal_clean_html(html: str) -> str:
    """
    Minimal HTML cleaning for full-HTML editing mode.
    
    Only removes comments and collapses excessive whitespace.
    Preserves all scripts, styles, hidden elements, and attributes.
    
    Args:
        html: Raw HTML content
        
    Returns:
        Minimally cleaned HTML string
        
    Raises:
        HTMLParseError: If HTML cannot be parsed
    """
    try:
        # Remove HTML comments
        html_str = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # Collapse excessive whitespace (but preserve single spaces)
        html_str = re.sub(r'\s+', ' ', html_str)
        html_str = re.sub(r'>\s+<', '><', html_str)
        
        return html_str.strip()
    except Exception as e:
        raise HTMLParseError(f"Failed to clean HTML: {e}")


def strip_large_text_nodes(soup: BeautifulSoup, max_length: int = 80) -> None:
    """
    Replace large text nodes with placeholders.
    
    Useful for structure-focused tasks where content doesn't matter.
    
    Args:
        soup: BeautifulSoup object to modify in-place
        max_length: Maximum text length before replacement
    """
    for element in soup.find_all(string=True):
        if isinstance(element, str) and len(element.strip()) > max_length:
            parent = element.parent
            if parent and parent.name not in ["script", "style"]:
                placeholder = f"[text:{len(element.strip())} chars]"
                element.replace_with(placeholder)

# Made with Bob
