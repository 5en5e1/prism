"""Element ID anchoring for stable references."""
import hashlib
from typing import Any

from bs4 import BeautifulSoup, Tag


def assign_element_ids(html: str) -> tuple[str, dict[str, str]]:
    """
    Assign stable short IDs to all meaningful elements.
    
    Args:
        html: HTML content to process
        
    Returns:
        Tuple of (modified HTML, element_id_map)
        where element_id_map is {element_id: css_selector}
    """
    soup = BeautifulSoup(html, "lxml")
    element_id_map: dict[str, str] = {}
    counter = 0

    # Process all meaningful elements
    for element in soup.find_all(True):
        if not isinstance(element, Tag):
            continue

        # Skip script and style tags
        if element.name in ["script", "style", "head", "meta", "link"]:
            continue

        # Generate element ID
        element_id = f"e{counter}"
        counter += 1

        # Add ID anchor attribute
        element["data-element-id"] = element_id

        # Generate CSS selector for this element
        selector = _generate_selector(element)
        element_id_map[element_id] = selector

    return str(soup), element_id_map


def _generate_selector(element: Tag) -> str:
    """
    Generate a stable CSS selector for an element.
    
    Priority order for stability across page reloads:
    1. ID (most stable)
    2. Unique class combinations
    3. Semantic attributes (role, aria-label)
    4. Data attributes
    5. Tag with nth-child (least stable)
    """
    # Priority 1: ID (most stable)
    if element.get("id"):
        return f"#{element['id']}"
    
    # Priority 2: Unique class combinations
    classes = element.get("class", [])
    if classes:
        if isinstance(classes, str):
            classes = [classes]
        class_str = ".".join(classes)
        selector = f"{element.name}.{class_str}"
        return selector
    
    # Priority 3: Semantic attributes (good for accessibility-focused sites)
    role = element.get("role")
    if role and isinstance(role, str):
        return f"{element.name}[role='{role}']"
    
    aria_label = element.get("aria-label")
    if aria_label and isinstance(aria_label, str):
        # Escape quotes in aria-label
        label = aria_label.replace("'", "\\'")
        return f"{element.name}[aria-label='{label}']"
    
    # Priority 4: Data attributes (often stable, excluding our own)
    for attr in element.attrs:
        if attr.startswith("data-") and attr != "data-element-id":
            value = element[attr]
            if isinstance(value, str):
                value = value.replace("'", "\\'")
                return f"{element.name}[{attr}='{value}']"
    
    # Priority 5: Tag with nth-child (least stable, fallback only)
    parent = element.parent
    if parent and parent.name != "[document]":
        siblings = [s for s in parent.children if isinstance(s, Tag) and s.name == element.name]
        if len(siblings) > 1:
            index = siblings.index(element) + 1
            return f"{element.name}:nth-child({index})"
    
    # Final fallback: just the tag name
    return element.name


def resolve_element_ids(element_id_map: dict[str, str], element_ids: list[str]) -> list[str]:
    """
    Resolve element IDs to CSS selectors.
    
    Args:
        element_id_map: Mapping from element IDs to selectors
        element_ids: List of element IDs to resolve
        
    Returns:
        List of CSS selectors
    """
    return [element_id_map.get(eid, "") for eid in element_ids]
