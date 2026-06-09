"""Anchored DOM + compact, token-budgeted skeleton for patch-based editing.

The model never sees or reproduces full HTML. Instead:

1. Every meaningful element in the original DOM is tagged with a stable
   ``data-be`` anchor id and kept server-side (full fidelity).
2. A compact one-line-per-element skeleton is produced for the model. Long
   text is truncated, script/style/SVG bodies are dropped, and runs of
   structurally identical siblings are collapsed (``... +213 more``) so that
   feed-style pages (YouTube, infinite lists) stay small.
3. The model returns patches that reference anchor ids; the applier resolves
   them against the original DOM.

This keeps both input (skeleton << full HTML) and output (patches << full
HTML) tokens bounded regardless of page size.
"""
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from ..ai.token_counter import count_tokens
from ..core.tracing import get_logger

logger = get_logger(__name__)

ANCHOR_ATTR = "data-be"

# Tags that carry no structure the model can usefully patch; omitted from the
# skeleton (they still remain in the DOM and are restored verbatim on output).
_SKIP_SKELETON = {
    "script", "style", "noscript", "template", "svg", "path", "meta",
    "link", "br", "hr", "head",
}

# Attributes worth showing the model, in a stable order. ``class``/``id`` are
# rendered specially; ``data-*`` (except our anchor) are always included.
# ``style`` is included so the model can preserve/extend existing inline CSS.
_ATTR_WHITELIST = (
    "style", "href", "src", "type", "name", "role", "placeholder", "value",
    "title", "alt", "aria-label", "for", "action", "method", "target", "rel",
)

# Verbose profile = the original limits (exact rollback target).
_MAX_CLASSES = 12
_ATTR_VALUE_LIMIT = 120
_STYLE_VALUE_LIMIT = 240
_DEFAULT_TEXT_LIMIT = 120
_DEFAULT_SIBLING_SAMPLE = 4
# Only collapse genuinely large sibling runs (feeds/lists). Small runs are
# shown in full so the model can address each element.
_COLLAPSE_THRESHOLD = 10
_INDENT_CAP = 40


@dataclass(frozen=True)
class SkeletonProfile:
    """Tunable limits for skeleton density. Affects only the model-facing
    text, never the id_map / selectors / apply path."""

    max_classes: int
    attr_limit: int
    style_limit: int
    text_limit: int
    sibling_sample: int
    collapse_threshold: int


# Verbose: byte-identical to the prior skeleton (DOM_SKELETON_COMPACT=false).
VERBOSE_PROFILE = SkeletonProfile(
    max_classes=_MAX_CLASSES,
    attr_limit=_ATTR_VALUE_LIMIT,
    style_limit=_STYLE_VALUE_LIMIT,
    text_limit=_DEFAULT_TEXT_LIMIT,
    sibling_sample=_DEFAULT_SIBLING_SAMPLE,
    collapse_threshold=_COLLAPSE_THRESHOLD,
)
# Compact: fewer tokens; still ample to identify/disambiguate elements.
COMPACT_PROFILE = SkeletonProfile(
    max_classes=5,
    attr_limit=64,
    style_limit=140,
    text_limit=64,
    sibling_sample=3,
    collapse_threshold=6,
)


@dataclass
class AnchoredDoc:
    """Result of skeletonization: keep ``soup``/``id_map`` for the applier."""

    soup: BeautifulSoup
    id_map: dict[str, Tag]
    skeleton: str
    css_context: str = ""
    stats: dict = field(default_factory=dict)
    truncated: bool = False


def extract_css_context(soup: BeautifulSoup, char_budget: int = 24_000) -> str:
    """Summarize the page's styling so edits stay design-consistent.

    Includes inline ``<style>`` rules (the design system) and external
    stylesheet hrefs (so the model knows there is CSS it cannot see and
    should prefer class-based edits). Bounded so it never dominates the
    prompt.
    """
    blocks: list[str] = []

    links = [
        str(l.get("href"))
        for l in soup.find_all("link")
        if isinstance(l, Tag)
        and "stylesheet" in (l.get("rel") or [])
        and l.get("href")
    ]
    if links:
        blocks.append(
            "External stylesheets (rules NOT shown - prefer editing via "
            "existing classes / inline style):\n"
            + "\n".join(f"- {h}" for h in links[:20])
        )

    css_parts: list[str] = []
    used = 0
    for style in soup.find_all("style"):
        if not isinstance(style, Tag):
            continue
        css = " ".join((style.get_text() or "").split())
        if not css:
            continue
        remaining = char_budget - used
        if remaining <= 0:
            css_parts.append("/* â€¦ additional <style> rules omitted */")
            break
        if len(css) > remaining:
            css = css[:remaining] + " /* â€¦truncated */"
        css_parts.append(css)
        used += len(css)
    if css_parts:
        blocks.append("Inline <style> rules:\n" + "\n".join(css_parts))

    return "\n\n".join(blocks)


_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "in", "on", "for", "with",
    "make", "change", "set", "this", "that", "it", "page", "all", "into",
    "please", "can", "you", "my", "is", "be", "as", "at", "by", "from",
}


def _prompt_terms(prompt: str) -> set[str]:
    """Lowercased content words from the user prompt, for relevance biasing."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", (prompt or "").lower())
    return {w for w in words if w not in _STOPWORDS}


_REL_ATTRS = ("aria-label", "title", "alt", "name", "href", "placeholder", "id")
_REL_MAX_DESC = 40  # cap descendants scanned per element (perf bound)


def _relevance(tag: Tag, terms: set[str]) -> int:
    """How many prompt terms match this element OR its near descendants.

    The thing the user names (e.g. a class on a child button) is often on a
    descendant, so we scan a bounded number of them. Still O(1)-ish per
    element so it stays fast on 500k-node pages.
    """
    if not terms:
        return 0
    parts: list[str] = []
    nodes = [tag]
    for d in tag.descendants:
        if isinstance(d, Tag):
            nodes.append(d)
            if len(nodes) >= _REL_MAX_DESC:
                break
    for n in nodes:
        parts.extend(_norm_classes(n))
        for name in _REL_ATTRS:
            v = n.get(name)
            if isinstance(v, str) and v:
                parts.append(v)
    blob = (" ".join(parts) + " " + tag.get_text(" ", strip=True)[:160]).lower()
    return sum(1 for t in terms if t in blob)


def _norm_classes(tag: Tag) -> tuple[str, ...]:
    classes = tag.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()
    return tuple(classes)


def _signature(tag: Tag) -> tuple:
    """Sibling-collapse key.

    Same tag + same class set => structurally "the same" (feed cards, list
    items). Elements with an ``id`` are individually addressable and
    semantically distinct, so they never collapse together.
    """
    el_id = tag.get("id")
    if isinstance(el_id, str) and el_id:
        return (tag.name, _norm_classes(tag), id(tag))  # unique => no collapse
    return (tag.name, _norm_classes(tag))


def _truncate(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) > limit:
        return value[: limit - 1] + "â€¦"
    return value


def _render_attrs(tag: Tag, p: "SkeletonProfile") -> str:
    parts: list[str] = []
    classes = _norm_classes(tag)
    if classes:
        shown = classes[: p.max_classes]
        suffix = "â€¦" if len(classes) > p.max_classes else ""
        parts.append("." + ".".join(shown) + suffix)
    el_id = tag.get("id")
    if isinstance(el_id, str) and el_id:
        parts.append("#" + el_id)

    kv: list[str] = []
    for name in _ATTR_WHITELIST:
        val = tag.get(name)
        if val is None:
            continue
        if isinstance(val, list):
            val = " ".join(val)
        limit = p.style_limit if name == "style" else p.attr_limit
        kv.append(f"{name}={_truncate(str(val), limit)}")
    for name, val in tag.attrs.items():
        if name.startswith("data-") and name != ANCHOR_ATTR:
            if isinstance(val, list):
                val = " ".join(val)
            kv.append(f"{name}={_truncate(str(val), p.attr_limit)}")

    head = "".join(parts)
    if kv:
        head += " [" + " ".join(kv) + "]"
    return head


def _direct_text(tag: Tag, limit: int) -> str:
    chunks = [
        str(c) for c in tag.children if isinstance(c, NavigableString)
    ]
    text = " ".join(chunks).strip()
    if not text:
        return ""
    return ' "' + _truncate(text, limit) + '"'


def build_anchored_skeleton(
    html: str,
    token_budget: int,
    *,
    model: str = "gpt-4o",
    profile: "SkeletonProfile | None" = None,
    prompt: str = "",
) -> AnchoredDoc:
    """Parse ``html``, anchor every element, and emit a budgeted skeleton.

    ``profile`` controls density (defaults to compact/verbose per
    ``settings.dom_skeleton_compact``). ``prompt`` (the user request) drives
    relevance-biased collapse so the elements being asked about stay visible
    on huge pages. ``truncated`` is set when the page is too large to fully
    represent within ``token_budget`` even after collapsing.
    """
    if profile is None:
        from ..config import settings

        profile = (
            COMPACT_PROFILE if settings.dom_skeleton_compact else VERBOSE_PROFILE
        )
    text_limit = profile.text_limit
    sibling_sample = profile.sibling_sample
    soup = BeautifulSoup(html, "lxml")

    # Drop HTML comments only. We deliberately do NOT collapse whitespace:
    # the parsed soup is what gets returned to the client, and collapsing
    # whitespace inside <script>/<pre>/<textarea> corrupts them (e.g. a JS
    # line // comment swallows the rest of the file once newlines are gone).
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    id_map: dict[str, Tag] = {}
    counter = 0
    for el in soup.find_all(True):
        if not isinstance(el, Tag):
            continue
        aid = str(counter)
        el[ANCHOR_ATTR] = aid
        id_map[aid] = el
        counter += 1

    terms = _prompt_terms(prompt)
    lines: list[str] = []
    # Running char estimate (~4 chars/token) avoids tokenizing every line on
    # 300k-token pages; a precise count is taken once at the end.
    budget_chars = token_budget * 4
    used_chars = 0
    state = {"truncated": False}

    root = soup.find("html") or soup

    def _collapse_params() -> tuple[int, int]:
        """Budget-aware (threshold, sample).

        While there is budget headroom we keep runs expanded (and sample
        generously) so big pages actually USE the budget instead of
        flattening to nothing; as we approach the limit we collapse harder.
        """
        pressure = used_chars / budget_chars if budget_chars else 1.0
        if pressure < 0.55:
            # Lots of room: only fold pathologically huge runs, and show a
            # generous sample (plus the relevance-picked ones) so the model
            # has real handles instead of a near-empty skeleton.
            return max(profile.collapse_threshold * 8, 60), 24
        if pressure < 0.80:
            return profile.collapse_threshold, profile.sibling_sample
        # Running out: fold everything aggressively to fit.
        return max(profile.collapse_threshold // 2, 3), 1

    def walk(tag: Tag, depth: int) -> None:
        if state["truncated"]:
            return
        if tag.name in _SKIP_SKELETON:
            return

        indent = " " * min(depth, _INDENT_CAP)
        aid = tag.get(ANCHOR_ATTR, "?")
        line = f"{indent}@{aid} {tag.name}{_render_attrs(tag, profile)}{_direct_text(tag, text_limit)}"

        nonlocal used_chars
        if used_chars + len(line) + 1 > budget_chars:
            state["truncated"] = True
            lines.append(
                f"{indent}â€¦ (skeleton truncated: page exceeds token budget)"
            )
            return
        used_chars += len(line) + 1
        lines.append(line)

        # Group consecutive element children by structural signature so feeds
        # and long lists collapse instead of exploding the skeleton.
        child_tags = [c for c in tag.children if isinstance(c, Tag)]
        i = 0
        while i < len(child_tags):
            if state["truncated"]:
                return
            sig = _signature(child_tags[i])
            run = [child_tags[i]]
            j = i + 1
            while j < len(child_tags) and _signature(child_tags[j]) == sig:
                run.append(child_tags[j])
                j += 1

            eff_threshold, eff_sample = _collapse_params()
            if len(run) > eff_threshold and child_tags[i].name not in _SKIP_SKELETON:
                # Choose which siblings to show: always the first (context),
                # then the most prompt-relevant ones, then fill in order.
                show = {0}
                if terms:
                    ranked = sorted(
                        range(len(run)),
                        key=lambda k: _relevance(run[k], terms),
                        reverse=True,
                    )
                    for k in ranked:
                        if len(show) >= eff_sample:
                            break
                        if _relevance(run[k], terms) > 0:
                            show.add(k)
                for k in range(len(run)):
                    if len(show) >= eff_sample:
                        break
                    show.add(k)

                shown_idx = sorted(show)
                for k in shown_idx:
                    walk(run[k], depth + 1)
                hidden = [run[k] for k in range(len(run)) if k not in show]
                if hidden:
                    ids = [int(h.get(ANCHOR_ATTR, "0")) for h in hidden]
                    child_indent = " " * min(depth + 1, _INDENT_CAP)
                    lines.append(
                        f"{child_indent}â€¦ +{len(hidden)} more <{sig[0]}> "
                        f"like @{run[0].get(ANCHOR_ATTR, '?')} "
                        f"(anchors @{min(ids)}..@{max(ids)})"
                    )
            else:
                for child in run:
                    walk(child, depth + 1)
            i = j

    if isinstance(root, Tag):
        walk(root, 0)
    else:  # pragma: no cover - lxml always yields a root tag
        for child in soup.children:
            if isinstance(child, Tag):
                walk(child, 0)

    skeleton = "\n".join(lines)
    css_context = extract_css_context(soup)
    skeleton_tokens = count_tokens(skeleton, model)
    css_tokens = count_tokens(css_context, model) if css_context else 0
    stats = {
        "original_size": len(html),
        "skeleton_size": len(skeleton),
        "element_count": counter,
        "skeleton_tokens": skeleton_tokens,
        "css_tokens": css_tokens,
        "token_budget": token_budget,
        "truncated": state["truncated"],
    }
    logger.info(
        "Anchored skeleton built: "
        f"{len(html)} bytes / {counter} elements -> "
        f"{len(skeleton)} bytes / ~{skeleton_tokens} tokens "
        f"(+{css_tokens} css tokens, truncated={state['truncated']})"
    )
    return AnchoredDoc(
        soup=soup,
        id_map=id_map,
        skeleton=skeleton,
        css_context=css_context,
        stats=stats,
        truncated=state["truncated"],
    )


def strip_anchors(soup: BeautifulSoup) -> None:
    """Remove the ``data-be`` anchor attribute from the final DOM."""
    for el in soup.find_all(attrs={ANCHOR_ATTR: True}):
        if isinstance(el, Tag):
            del el[ANCHOR_ATTR]
