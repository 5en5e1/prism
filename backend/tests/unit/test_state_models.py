"""Tests for explicit website/page/snapshot identity models."""
from app.state.models import canonicalize_page_identity, snapshot_for_html


def test_page_identity_keeps_semantic_query_params_separate():
    a = canonicalize_page_identity("https://example.com/products?id=1&utm_source=x")
    b = canonicalize_page_identity("https://example.com/products?id=2&utm_source=x")

    assert a.route_key == "/products?id=1"
    assert b.route_key == "/products?id=2"
    assert a.page_id != b.page_id


def test_page_identity_keeps_hash_routes_but_not_plain_anchors():
    route = canonicalize_page_identity("https://example.com/app#/settings")
    anchor = canonicalize_page_identity("https://example.com/app#section")

    assert route.route_key == "/app#/settings"
    assert anchor.route_key == "/app"


def test_snapshot_changes_with_navigation_epoch():
    identity = canonicalize_page_identity("https://example.com/docs")
    first = snapshot_for_html(
        page_url=identity.canonical_url,
        html="<html><body>A</body></html>",
        page_identity=identity,
        navigation_epoch=1,
    )
    second = snapshot_for_html(
        page_url=identity.canonical_url,
        html="<html><body>A</body></html>",
        page_identity=identity,
        navigation_epoch=2,
    )

    assert first.page_id == second.page_id
    assert first.snapshot_id != second.snapshot_id
