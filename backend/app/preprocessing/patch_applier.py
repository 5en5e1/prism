"""Apply anchor-id patches to the original DOM.

The model returns a list of patch ops keyed by ``data-be`` anchor id. We
resolve each id against the original (full-fidelity) soup and apply the edit
with BeautifulSoup. Application is best-effort: a bad/stale target skips that
one patch with a recorded reason instead of failing the whole request.
"""
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..core.tracing import get_logger
from .anchor_skeleton import ANCHOR_ATTR, strip_anchors

logger = get_logger(__name__)


def _parse_fragment(html: str) -> list[Any]:
    """Parse an HTML fragment into detached nodes.

    lxml wraps bare fragments in ``<html><body>``; we unwrap to return just
    the meaningful nodes so they can be reparented into the target soup.
    """
    frag = BeautifulSoup(html or "", "lxml")
    body = frag.find("body")
    container = body if isinstance(body, Tag) else frag
    return [n for n in list(container.children) if not _is_blank(n)]


def _is_blank(node: Any) -> bool:
    return getattr(node, "name", None) is None and not str(node).strip()


def _parse_style(style: str) -> dict[str, str]:
    decls: dict[str, str] = {}
    for part in (style or "").split(";"):
        if ":" in part:
            k, _, v = part.partition(":")
            k = k.strip().lower()
            if k:
                decls[k] = v.strip()
    return decls


def _merge_style(existing: str, incoming: str) -> str:
    """Merge ``incoming`` declarations over ``existing`` ones.

    Non-destructive: properties not mentioned in ``incoming`` are preserved,
    so a style edit never silently drops inline CSS the model didn't see.
    """
    merged = _parse_style(existing)
    merged.update(_parse_style(incoming))
    return "; ".join(f"{k}: {v}" for k, v in merged.items() if v) + (
        ";" if merged else ""
    )


def _attached(tag: Tag) -> bool:
    """True if the tag is still part of a document (not detached/removed)."""
    node: Any = tag
    while node is not None:
        if getattr(node, "name", None) == "[document]":
            return True
        node = node.parent
    return False


# Structural/raw-text elements whose contents the model never fully sees.
# Destructive ops here are the #1 cause of wiped stylesheets/scripts and
# missing page content, so they are refused outright.
_PROTECTED = {"html", "head", "body", "script", "style"}
_DESTRUCTIVE = {"replace_inner", "replace_element", "delete", "set_text"}


def _set_css_vars(soup: BeautifulSoup, vars_map: dict[str, str]) -> None:
    """Inject/refresh a single override stylesheet of :root custom props.

    Theming this way is non-destructive: the original <style> is untouched,
    and !important + last-in-head ordering beats author :root rules and even
    inline custom properties on <body>.
    """
    head = soup.find("head")
    if head is None:
        html = soup.find("html") or soup
        head = soup.new_tag("head")
        if isinstance(html, Tag):
            html.insert(0, head)
    style = soup.find("style", id="bob-overrides")
    if style is None:
        style = soup.new_tag("style", id="bob-overrides")
        head.append(style)
    decls = "".join(f"{k}:{v} !important;" for k, v in vars_map.items())
    style.string = f":root{{{decls}}}"


def apply_patches(
    soup: BeautifulSoup,
    id_map: dict[str, Tag],
    patches: list[Any],
) -> tuple[str, int, list[str]]:
    """Apply ``patches`` to ``soup`` in order.

    Returns ``(modified_html, applied_count, skipped_reasons)``.
    """
    applied = 0
    skipped: list[str] = []
    css_vars: dict[str, str] = {}

    def resolve(anchor_id: str) -> Tag | None:
        tag = id_map.get(str(anchor_id))
        if tag is None or not _attached(tag):
            return None
        return tag

    for patch in patches:
        op = patch.op
        try:
            if op == "set_css_var":
                name = patch.name
                if not name.startswith("--"):
                    name = "--" + name
                css_vars[name] = patch.value
                applied += 1
                continue

            # Refuse destructive ops on structural / raw-text elements.
            if op in _DESTRUCTIVE:
                _t = id_map.get(str(getattr(patch, "target", "")))
                if _t is not None and _t.name in _PROTECTED:
                    skipped.append(
                        f"{op} @{patch.target}: refused on <{_t.name}> "
                        "(protected; use set_css_var/set_attr instead)"
                    )
                    continue

            if op == "set_text":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(f"set_text @{patch.target}: not found/stale")
                    continue
                el.clear()
                el.append(patch.text)
                applied += 1

            elif op == "set_attr":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(f"set_attr @{patch.target}: not found/stale")
                    continue
                if patch.value is None:
                    el.attrs.pop(patch.name, None)
                else:
                    el[patch.name] = patch.value
                applied += 1

            elif op == "set_style":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(f"set_style @{patch.target}: not found/stale")
                    continue
                el["style"] = _merge_style(el.get("style", ""), patch.style)
                applied += 1

            elif op == "add_class":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(f"add_class @{patch.target}: not found/stale")
                    continue
                classes = el.get("class") or []
                if isinstance(classes, str):
                    classes = classes.split()
                if patch.class_name not in classes:
                    classes.append(patch.class_name)
                el["class"] = classes
                applied += 1

            elif op == "remove_class":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(
                        f"remove_class @{patch.target}: not found/stale"
                    )
                    continue
                classes = el.get("class") or []
                if isinstance(classes, str):
                    classes = classes.split()
                el["class"] = [c for c in classes if c != patch.class_name]
                applied += 1

            elif op == "replace_inner":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(
                        f"replace_inner @{patch.target}: not found/stale"
                    )
                    continue
                el.clear()
                for node in _parse_fragment(patch.html):
                    el.append(node)
                applied += 1

            elif op == "replace_element":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(
                        f"replace_element @{patch.target}: not found/stale"
                    )
                    continue
                nodes = _parse_fragment(patch.html)
                if not nodes:
                    skipped.append(
                        f"replace_element @{patch.target}: empty replacement"
                    )
                    continue
                el.replace_with(nodes[0])
                anchor = nodes[0]
                for node in nodes[1:]:
                    anchor.insert_after(node)
                    anchor = node
                applied += 1

            elif op == "insert":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(f"insert @{patch.target}: not found/stale")
                    continue
                nodes = _parse_fragment(patch.html)
                _place(el, nodes, patch.position)
                applied += 1

            elif op == "delete":
                el = resolve(patch.target)
                if el is None:
                    skipped.append(f"delete @{patch.target}: not found/stale")
                    continue
                el.decompose()
                applied += 1

            elif op == "move":
                el = resolve(patch.target)
                dest = resolve(patch.to)
                if el is None or dest is None:
                    skipped.append(
                        f"move @{patch.target}->@{patch.to}: not found/stale"
                    )
                    continue
                el.extract()
                _place(dest, [el], patch.position)
                applied += 1

            else:  # pragma: no cover - schema constrains op values
                skipped.append(f"unknown op '{op}'")
        except Exception as e:  # one bad patch must not sink the rest
            skipped.append(f"{op} @{getattr(patch, 'target', '?')}: {e}")
            logger.warning(f"Patch '{op}' failed: {e}")

    if css_vars:
        _set_css_vars(soup, css_vars)

    strip_anchors(soup)
    if skipped:
        logger.warning(
            f"Applied {applied} patches, skipped {len(skipped)}: {skipped[:10]}"
        )
    return str(soup), applied, skipped


def _place(ref: Tag, nodes: list[Any], position: str) -> None:
    """Insert ``nodes`` relative to ``ref`` per ``position``."""
    if position == "before":
        for n in nodes:
            ref.insert_before(n)
    elif position == "after":
        anchor: Any = ref
        for n in nodes:
            anchor.insert_after(n)
            anchor = n
    elif position == "prepend":
        for n in reversed(nodes):
            ref.insert(0, n)
    elif position == "append":
        for n in nodes:
            ref.append(n)
