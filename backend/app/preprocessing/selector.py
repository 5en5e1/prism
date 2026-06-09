"""Compute robust, browser-resolvable selectors for live-DOM patching.

We never reserialize the page. Instead each patch carries a CSS selector
(plus fallback hints) that the injected runtime resolves against the live,
post-JS DOM with ``querySelector``. Selectors are built from the parsed
snapshot but use only structural features (ids + ``:nth-of-type`` paths) that
remain valid in the rendered DOM.
"""
import re

from bs4 import Tag

_SAFE_ID = re.compile(r"^[A-Za-z_][-A-Za-z0-9_]*$")
_HINT_ATTRS = ("href", "src", "name", "type", "role", "aria-label", "alt")


def _id_step(tag: Tag) -> str | None:
    el_id = tag.get("id")
    if not isinstance(el_id, str) or not el_id:
        return None
    if _SAFE_ID.match(el_id):
        return f"#{el_id}"
    escaped = el_id.replace("\\", "\\\\").replace('"', '\\"')
    return f'{tag.name}[id="{escaped}"]'


def _nth_of_type(tag: Tag) -> str:
    parent = tag.parent
    if parent is None:
        return tag.name
    same = [c for c in parent.children if isinstance(c, Tag) and c.name == tag.name]
    if len(same) <= 1:
        return tag.name
    return f"{tag.name}:nth-of-type({same.index(tag) + 1})"


def robust_selector(tag: Tag, unique_ids: set[str]) -> str:
    """Build a unique selector, anchored at the closest unique-id ancestor.

    ``unique_ids`` is the set of ids that appear exactly once in the document
    (precomputed by the caller) so an id step is only trusted when it is
    genuinely unique.
    """
    steps: list[str] = []
    node: Tag | None = tag
    while node is not None and node.name not in ("[document]", None):
        el_id = node.get("id")
        if (
            isinstance(el_id, str)
            and el_id in unique_ids
            and (step := _id_step(node))
        ):
            steps.insert(0, step)
            return " > ".join(steps)  # id is unique -> absolute anchor
        steps.insert(0, _nth_of_type(node))
        node = node.parent if isinstance(node.parent, Tag) else None
    return " > ".join(steps)


def element_hint(tag: Tag) -> dict:
    """Fallback identity used if the selector fails on a drifted DOM."""
    text = " ".join(
        s.strip() for s in tag.strings if s.strip()
    )[:80]
    attrs = {}
    for a in _HINT_ATTRS:
        v = tag.get(a)
        if isinstance(v, str) and v:
            attrs[a] = v[:120]
    hint: dict = {"tag": tag.name}
    if text:
        hint["text"] = text
    if attrs:
        hint["attrs"] = attrs
    return hint


def compute_unique_ids(soup) -> set[str]:
    seen: dict[str, int] = {}
    for el in soup.find_all(True):
        if isinstance(el, Tag):
            i = el.get("id")
            if isinstance(i, str) and i:
                seen[i] = seen.get(i, 0) + 1
    return {k for k, n in seen.items() if n == 1}
