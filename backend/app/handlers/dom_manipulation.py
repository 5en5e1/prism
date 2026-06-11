"""DOM manipulation handler - anchored patch, live-DOM injection mode.

The model receives a compact anchored skeleton and returns a small JSON
patch list keyed by anchor id. By default ("inject") we return the original
HTML byte-for-byte plus a runtime <script> that applies those patches to the
live, post-JS DOM and re-asserts them across re-renders -- so it works for
static, dynamic, animated and SPA sites without any fidelity loss. A legacy
"server" mode (parse + reserialize) is kept for non-JS consumers.
"""
import json

from ..config import settings
from ..core.exceptions import MalformedResponseError, OversizeError, ValidationError
from ..core.registry import register_handler
from ..core.tracing import get_logger
from ..handlers.base import Handler, Message, ModelConfig, ProcessedContext
from ..preprocessing.anchor_skeleton import ANCHOR_ATTR, build_anchored_skeleton
from ..preprocessing.patch_applier import _DESTRUCTIVE, _PROTECTED, apply_patches
from ..preprocessing.selector import (
    compute_unique_ids,
    element_hint,
    robust_selector,
)
from ..prompts.loader import get_prompt_loader
from ..schemas.dom_manipulation import (
    DOMManipulationRequest,
    DOMManipulationResult,
    DOMPatchResult,
)
from ..state.models import PageIdentity, canonicalize_page_identity, snapshot_for_html

logger = get_logger(__name__)


def _compact_text(value: object, limit: int = 160) -> str:
    return " ".join(str(value or "").split())[:limit]


def _classes(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        return [item for item in value.split() if item]
    return []


def _tag_text(tag, limit: int = 240) -> str:
    return _compact_text(tag.get_text(" ", strip=True) if tag else "", limit)


def _selected_text(element: dict, limit: int = 240) -> str:
    return _compact_text(element.get("visibleText") or "", limit)


def _score_selected_candidate(tag, element: dict) -> int:
    score = 0
    if not tag:
        return score

    selected_id = str(element.get("id") or "")
    if selected_id and tag.get("id") == selected_id:
        score += 60

    selected_tag = str(element.get("tagName") or "").lower()
    if selected_tag and tag.name == selected_tag:
        score += 20

    selected_classes = set(_classes(element.get("classes")))
    tag_classes = set(_classes(tag.get("class", [])))
    score += min(len(selected_classes & tag_classes), 6) * 8

    selected_text = _selected_text(element)
    tag_text = _tag_text(tag)
    if selected_text and tag_text:
        if selected_text == tag_text:
            score += 45
        elif selected_text in tag_text or tag_text in selected_text:
            score += 24

    for name, value in (element.get("attributes") or {}).items():
        if value and str(tag.get(name) or "") == str(value):
            score += 10
    for name, value in (element.get("dataAttributes") or {}).items():
        if value and str(tag.get(name) or "") == str(value):
            score += 12

    return score


def _resolve_selected_element(soup, element: dict):
    candidates = []

    for selector in element.get("selectorCandidates") or []:
        try:
            matches = soup.select(selector)
        except Exception:
            matches = []
        candidates.extend(matches)
        if len(matches) == 1:
            return matches[0], "unique selector", _score_selected_candidate(matches[0], element)

    selected_id = str(element.get("id") or "")
    if selected_id:
        match = soup.find(id=selected_id)
        if match is not None:
            candidates.append(match)

    tag_name = str(element.get("tagName") or "").lower()
    class_names = _classes(element.get("classes"))[:3]
    if tag_name and class_names:
        try:
            candidates.extend(soup.select(f"{tag_name}.{'.'.join(class_names)}"))
        except Exception:
            pass

    ranked = sorted(
        ({id(candidate): candidate for candidate in candidates}.values()),
        key=lambda candidate: _score_selected_candidate(candidate, element),
        reverse=True,
    )
    if not ranked:
        return None, "unresolved", 0

    best = ranked[0]
    best_score = _score_selected_candidate(best, element)
    second_score = _score_selected_candidate(ranked[1], element) if len(ranked) > 1 else -1
    if best_score >= 32 and best_score > second_score:
        return best, "scored match", best_score

    return None, "ambiguous", best_score


def _compact_json(value: object, limit: int = 900) -> str:
    text = json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))
    return text[:limit]


def _selected_capture_summary(element: dict) -> dict:
    return {
        "capturedTag": element.get("tagName") or "",
        "capturedId": element.get("id") or "",
        "capturedClasses": (element.get("classes") or [])[:6],
        "visibleText": _selected_text(element, 180),
        "attributes": element.get("attributes") or {},
        "dataAttributes": element.get("dataAttributes") or {},
        "boundingBox": element.get("boundingBox") or {},
        "computedStyles": element.get("computedStyles") or {},
        "domContext": element.get("domContext") or {},
        "screenshotContext": element.get("screenshotContext") or {},
    }


def _selected_element_context(soup, selected_elements: list[dict]) -> str:
    """Resolve popup-selected element references to skeleton anchor ids."""

    selected_elements = [element for element in (selected_elements or []) if element.get("reference")]
    if not selected_elements:
        return ""

    lines: list[str] = []
    lines.extend([
        "Selection resolution policy:",
        "- Treat selected elements as precise user targets, not suggestions.",
        "- If there is one selected element, vague words like this/it/selected element target that element.",
        "- If there are multiple selected elements, quoted references target exact elements; these/all selected targets all selected elements.",
        "- If multiple elements are selected and the prompt uses singular this/it without a reference, target the most recently selected element.",
        "- Prefer the resolved @anchor ids below. Only choose another element if the selected target is unresolved.",
        "",
        "Resolved selected targets:",
    ])

    latest_reference = str(selected_elements[-1].get("reference") or "").strip()
    for element in selected_elements:
        reference = str(element.get("reference") or "").strip()
        if not reference:
            continue
        resolved, resolution, score = _resolve_selected_element(soup, element)
        if resolved is None:
            lines.append(
                f"- '{reference}' could not be resolved ({resolution}, score={score}). "
                f"Captured context={_compact_json(_selected_capture_summary(element), 1000)}"
            )
            continue
        anchor = resolved.get(ANCHOR_ATTR)
        text = " ".join((resolved.get_text(" ", strip=True) or "").split())[:120]
        tag = resolved.name
        dom_id = resolved.get("id", "")
        classes = ".".join(resolved.get("class", [])[:4])
        label = f"<{tag}{'#' + dom_id if dom_id else ''}{'.' + classes if classes else ''}>"
        latest = " latest-selected" if reference == latest_reference else ""
        lines.append(
            f"- '{reference}'{latest} => @{anchor} {label}; "
            f"resolution={resolution}; score={score}; resolvedText={text!r}; "
            f"capturedContext={_compact_json(_selected_capture_summary(element), 1200)}"
        )
    return "\n".join(lines)


@register_handler("dom_manipulation")
class DOMManipulationHandler(Handler[DOMManipulationRequest, DOMManipulationResult]):
    """Handler for DOM manipulation via anchored patches."""

    @property
    def name(self) -> str:
        return "dom_manipulation"

    @property
    def request_model(self) -> type[DOMManipulationRequest]:
        return DOMManipulationRequest

    @property
    def response_model(self) -> type[DOMManipulationResult]:
        return DOMManipulationResult

    @property
    def model_config(self) -> ModelConfig:
        return ModelConfig(
            model=settings.openai_default_model,
            temperature=0.2,
            # Patches are intent, not full HTML, so the output budget stays
            # small even for very large pages.
            max_completion_tokens=settings.dom_max_patch_tokens,
            response_format="json_schema",
            reasoning_effort=settings.openai_reasoning_effort,
        )

    async def preprocess(
        self, html: str, params: DOMManipulationRequest
    ) -> ProcessedContext:
        """Anchor the DOM and build a token-budgeted skeleton.

        The full soup + anchor map are stashed in ``metadata`` for the
        applier. Pages too large to represent within the budget are rejected
        rather than silently truncated into a wrong edit.
        """
        logger.info("Building anchored skeleton for patch-based editing")

        # Pass raw HTML straight through. The skeleton (not this HTML) is
        # what the model sees; the parsed DOM is what we return, so it must
        # stay byte-faithful (scripts/styles/pre intact).
        doc = build_anchored_skeleton(
            html,
            token_budget=settings.dom_skeleton_token_budget,
            model=settings.openai_default_model,
            prompt=params.user_prompt,
        )

        if doc.truncated:
            raise OversizeError(
                "Page is too large to represent within the skeleton token "
                f"budget ({settings.dom_skeleton_token_budget} tokens, "
                f"{doc.stats['element_count']} elements). Increase "
                "DOM_SKELETON_TOKEN_BUDGET or scope the request to a "
                "smaller region.",
                retryable=False,
            )

        logger.info(
            f"Skeleton ready: {doc.stats['original_size']} bytes / "
            f"{doc.stats['element_count']} elements -> "
            f"~{doc.stats['skeleton_tokens']} tokens"
        )

        return ProcessedContext(
            processed_html=doc.skeleton,
            element_id_map={},
            original_size=doc.stats["original_size"],
            processed_size=doc.stats["skeleton_size"],
            chunk_count=1,
            metadata={
                "patch_mode": True,
                "soup": doc.soup,
                "id_map": doc.id_map,
                "original_html": html,
                "css_context": doc.css_context,
                "skeleton_stats": doc.stats,
                "page_identity": params.page_identity,
                "page_snapshot": params.page_snapshot,
                "selected_elements_context": _selected_element_context(
                    doc.soup,
                    params.params.selected_elements,
                ),
            },
        )

    async def build_messages(
        self, context: ProcessedContext, params: DOMManipulationRequest, user_prompt: str
    ) -> list[Message]:
        """Build messages: patch protocol system prompt + skeleton."""
        loader = get_prompt_loader()

        system_content = loader.render_template("dom_manipulation", "system")
        if not system_content:
            raise ValueError("System template not found for dom_manipulation")

        user_content = loader.render_template(
            "dom_manipulation",
            "user",
            user_prompt=user_prompt,
            skeleton=context.processed_html,
            css_context=context.metadata.get("css_context", ""),
            selected_elements_context=context.metadata.get("selected_elements_context", ""),
        )
        if not user_content:
            raise ValueError("User template not found for dom_manipulation")

        return [
            Message(role="system", content=system_content),
            Message(role="user", content=user_content),
        ]

    async def parse_response(
        self, raw_response: str, context: ProcessedContext
    ) -> DOMPatchResult:
        """Parse the JSON patch list returned by the model."""
        text = raw_response.strip()
        # Defensive: tolerate ```json fences even though JSON mode is on.
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[: text.rfind("```")]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise MalformedResponseError(f"Invalid JSON: {e}")

        try:
            return DOMPatchResult.model_validate(data)
        except Exception as e:
            raise ValidationError(f"Patch list validation failed: {e}")

    async def postprocess(
        self, parsed: DOMPatchResult, context: ProcessedContext
    ) -> DOMManipulationResult:
        """Resolve patches to live-DOM ops + a server-applied fallback.

        Primary output is ``patches`` + ``css_vars``: the extension applies
        these to the live, post-JS DOM in place (scripts/listeners/SPA state
        preserved). ``modified_html`` is a lossy server-applied fallback for
        non-JS consumers only.
        """
        soup = context.metadata["soup"]
        id_map = context.metadata["id_map"]
        unique_ids = compute_unique_ids(soup)
        client_identity = context.metadata.get("page_identity") or {}
        client_snapshot = context.metadata.get("page_snapshot") or {}
        page_url = client_snapshot.get("pageUrl") or client_identity.get("canonicalUrl") or ""
        if client_identity.get("pageId"):
            identity = PageIdentity(
                page_id=client_identity["pageId"],
                website_id=client_identity.get("websiteId", ""),
                origin=client_identity.get("origin", ""),
                path=client_identity.get("path", "/"),
                route_key=client_identity.get("routeKey", "/"),
                canonical_url=client_identity.get("canonicalUrl", page_url),
                viewport_variant=client_identity.get("viewportVariant", "default"),
                auth_variant=client_identity.get("authVariant", "unknown"),
            )
        else:
            identity = canonicalize_page_identity(page_url or "about:blank")
        snapshot = snapshot_for_html(
            page_url=page_url or identity.canonical_url,
            html=context.metadata.get("original_html", ""),
            page_identity=identity,
            navigation_epoch=int(client_snapshot.get("navigationEpoch") or 0),
            element_count=int(client_snapshot.get("elementCount") or 0),
            metadata=client_snapshot,
        )

        ops: list[dict] = []
        css_vars: dict[str, str] = {}
        css_rules: list[str] = []
        skipped: list[str] = []
        edit_records: list[dict] = []

        # Resolve selectors BEFORE apply_patches mutates/strips the soup.
        for i, patch in enumerate(parsed.patches):
            op = patch.op
            if op == "set_css_var":
                name = patch.name if patch.name.startswith("--") else f"--{patch.name}"
                css_vars[name] = patch.value
                continue
            if op == "add_css_rule":
                if patch.css.strip():
                    css_rules.append(patch.css.strip())
                continue

            tag = id_map.get(str(getattr(patch, "target", "")))
            if tag is None:
                skipped.append(f"{op} @{getattr(patch,'target','?')}: unknown anchor")
                continue
            if op in _DESTRUCTIVE and tag.name in _PROTECTED:
                skipped.append(f"{op} @{patch.target}: refused on <{tag.name}>")
                continue

            entry: dict = {
                "id": f"p{i}",
                "op": op,
                "s": robust_selector(tag, unique_ids),
                "h": element_hint(tag),
                "pageId": identity.page_id,
                "snapshotId": snapshot.snapshot_id,
            }
            for field in ("text", "name", "value", "style", "class_name",
                          "html", "position"):
                if hasattr(patch, field):
                    entry[field] = getattr(patch, field)
            if op == "move":
                dest = id_map.get(str(patch.to))
                if dest is None:
                    skipped.append(f"move @{patch.target}: unknown dest @{patch.to}")
                    continue
                entry["t"] = robust_selector(dest, unique_ids)
            ops.append(entry)
            edit_records.append({
                "operationId": entry["id"],
                "pageId": identity.page_id,
                "snapshotId": snapshot.snapshot_id,
                "elementInstanceId": (
                    f"{identity.page_id}:{snapshot.snapshot_id}:"
                    f"{getattr(patch, 'target', '')}"
                ),
                "componentId": None,
                "targetScope": "page",
                "operationType": op,
                "beforeState": {"selectorCandidates": [entry["s"]], "hint": entry["h"]},
                "afterState": {
                    key: entry[key]
                    for key in ("text", "name", "value", "style", "class_name", "html", "position")
                    if key in entry
                },
                "selectorCandidates": [entry["s"]],
                "expectedElementFingerprint": entry["h"],
                "verificationRule": {
                    "structural": ["target_exists", "fingerprint_matches"],
                    "visual": ["visible_when_expected"],
                },
                "rollbackPath": "restore beforeState on the same pageId/snapshot lineage",
                "status": "planned",
            })

        # Optional lossy fallback for non-JS consumers. OFF by default: the
        # extension applies `patches` to the live DOM and never reads this,
        # while building it runs a slow reserialize and bloats the response
        # enough to stall the extension's offscreen->worker message on big
        # pages (job stuck on "processing").
        if settings.dom_emit_server_html:
            modified_html, _, _ = apply_patches(soup, id_map, parsed.patches)
        else:
            modified_html = ""

        applied = len(ops) + len(css_vars) + len(css_rules)
        summary = parsed.changes_summary or "Applied DOM patches."
        if skipped:
            summary += f" ({applied} applied, {len(skipped)} skipped)"

        logger.info(
            f"Resolved {len(ops)} ops + {len(css_vars)} css vars + "
            f"{len(css_rules)} css rules, {len(skipped)} skipped "
            f"(live-DOM patch response)"
        )

        return DOMManipulationResult(
            patches=ops,
            css_vars=css_vars,
            css_rules=css_rules,
            skipped=skipped,
            page_identity=identity.model_dump(),
            snapshot=snapshot.model_dump(mode="json"),
            edit_records=edit_records,
            modified_html=modified_html,
            changes_summary=summary,
            original_size=context.original_size,
            modified_size=len(modified_html),
        )
