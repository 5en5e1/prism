"""HTML skeletonization for structure-focused tasks."""
from bs4 import BeautifulSoup, NavigableString, Tag


def skeletonize_html(html: str, max_text_length: int = 80) -> str:
    """
    Reduce HTML to structural skeleton by replacing long text with placeholders.
    
    This is useful for DOM manipulation and redesign tasks where the structure
    matters more than the actual content.
    
    Args:
        html: HTML content to skeletonize
        max_text_length: Maximum text length before replacement
        
    Returns:
        Skeletonized HTML string
    """
    soup = BeautifulSoup(html, "lxml")

    # Replace long text nodes with placeholders
    for element in soup.descendants:
        if isinstance(element, NavigableString) and not isinstance(element, type(soup)):
            text = str(element).strip()
            if len(text) > max_text_length:
                parent = element.parent
                if parent and isinstance(parent, Tag) and parent.name not in ["script", "style"]:
                    placeholder = f"[text:{len(text)} chars]"
                    element.replace_with(placeholder)

    return str(soup)


def extract_skeleton(html: str, max_depth: int = 3) -> str:
    """
    Extract a shallow skeleton of the HTML structure.
    
    Useful for two-pass processing where we first identify relevant sections.
    
    Args:
        html: HTML content
        max_depth: Maximum depth to preserve
        
    Returns:
        Skeleton HTML with deep branches truncated
    """
    soup = BeautifulSoup(html, "lxml")

    def truncate_deep_branches(element: Tag, current_depth: int = 0) -> None:
        """Recursively truncate branches deeper than max_depth."""
        if current_depth >= max_depth:
            # Replace deep content with placeholder
            element.clear()
            element.string = f"[{len(list(element.descendants))} nested elements]"
            return

        for child in list(element.children):
            if isinstance(child, Tag):
                truncate_deep_branches(child, current_depth + 1)

    # Start from body if it exists, otherwise from root
    body = soup.find("body")
    if body and isinstance(body, Tag):
        truncate_deep_branches(body, 0)
    else:
        truncate_deep_branches(soup, 0)

    return str(soup)

# Made with Bob
