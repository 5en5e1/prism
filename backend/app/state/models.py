"""Website/page/snapshot identity models.

These models intentionally separate persisted page state from browser runtime
state. A reusable component can link many page-specific element instances, but
it never replaces those instances.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {"fbclid", "gclid", "msclkid"}


class PageIdentity(BaseModel):
    """Canonical identity for one page/subpath/route variant."""

    page_id: str
    website_id: str
    origin: str
    path: str
    route_key: str
    canonical_url: str
    query_policy: Literal["semantic"] = "semantic"
    hash_policy: Literal["route-only"] = "route-only"
    viewport_variant: str = "default"
    auth_variant: str = "unknown"


class PageSnapshot(BaseModel):
    """One captured state of a page at a navigation epoch."""

    snapshot_id: str
    page_id: str
    page_url: str
    navigation_epoch: int = 0
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    html_sha256: str
    element_count: int = 0
    sources: list[str] = Field(
        default_factory=lambda: [
            "live_dom",
            "computed_styles_layout",
            "accessibility_semantics",
            "visual_viewport",
            "raw_html_archive",
        ]
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ElementInstance(BaseModel):
    """Concrete element on one concrete page snapshot."""

    element_instance_id: str
    page_id: str
    snapshot_id: str
    selector_candidates: list[str] = Field(default_factory=list)
    semantic_fingerprint: str = ""
    structural_fingerprint: str = ""
    component_id: str | None = None


class ComponentDefinition(BaseModel):
    """Reusable component inferred from page-specific instances."""

    component_id: str
    website_id: str
    name: str = ""
    instance_ids: list[str] = Field(default_factory=list)


class WebsiteState(BaseModel):
    """Domain/project-level persisted state."""

    website_id: str
    origin: str
    known_page_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)


class BrowserSessionState(BaseModel):
    """Temporary tab/session state. Never persisted as edit memory."""

    tab_id: int | None = None
    current_url: str
    navigation_epoch: int = 0
    route_key: str
    live_dom_valid: bool = True


def _semantic_query(search: str) -> str:
    pairs = []
    for key, value in parse_qsl(search.lstrip("?"), keep_blank_values=True):
        lower = key.lower()
        if lower in TRACKING_QUERY_NAMES or lower.startswith(TRACKING_QUERY_PREFIXES):
            continue
        pairs.append((key, value))
    return urlencode(sorted(pairs), doseq=True)


def _route_hash(fragment: str) -> str:
    if fragment.startswith("/") or fragment.startswith("!"):
        return fragment
    return ""


def canonicalize_page_identity(
    url: str,
    *,
    viewport_variant: str = "default",
    auth_variant: str = "unknown",
) -> PageIdentity:
    """Build a stable page identity without collapsing distinct routes."""

    parsed = urlsplit(url)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else parsed.scheme
    path = parsed.path or "/"
    query = _semantic_query(parsed.query)
    route_hash = _route_hash(parsed.fragment)
    route_key = path
    if query:
        route_key = f"{route_key}?{query}"
    if route_hash:
        route_key = f"{route_key}#{route_hash}"

    canonical_url = urlunsplit((parsed.scheme, parsed.netloc, path, query, route_hash))
    website_id = sha256(origin.encode("utf-8")).hexdigest()[:16]
    page_basis = f"{origin}|{route_key}|{viewport_variant}|{auth_variant}"
    page_id = sha256(page_basis.encode("utf-8")).hexdigest()[:24]
    return PageIdentity(
        page_id=page_id,
        website_id=website_id,
        origin=origin,
        path=path,
        route_key=route_key,
        canonical_url=canonical_url,
        viewport_variant=viewport_variant,
        auth_variant=auth_variant,
    )


def snapshot_for_html(
    *,
    page_url: str,
    html: str,
    page_identity: PageIdentity | None = None,
    navigation_epoch: int = 0,
    element_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> PageSnapshot:
    """Create a deterministic snapshot record for captured page state."""

    identity = page_identity or canonicalize_page_identity(page_url)
    html_hash = sha256(html.encode("utf-8")).hexdigest()
    snapshot_basis = f"{identity.page_id}|{navigation_epoch}|{html_hash}"
    return PageSnapshot(
        snapshot_id=sha256(snapshot_basis.encode("utf-8")).hexdigest()[:24],
        page_id=identity.page_id,
        page_url=page_url,
        navigation_epoch=navigation_epoch,
        html_sha256=html_hash,
        element_count=element_count,
        metadata=metadata or {},
    )
