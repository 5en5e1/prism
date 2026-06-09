"""Tests for the anchored skeleton + patch applier pipeline."""
from app.preprocessing.anchor_skeleton import (
    ANCHOR_ATTR,
    build_anchored_skeleton,
)
from app.preprocessing.patch_applier import apply_patches
from app.schemas.dom_manipulation import (
    AddClassOp,
    DeleteOp,
    InsertOp,
    MoveOp,
    ReplaceInnerOp,
    SetAttrOp,
    SetCssVarOp,
    SetStyleOp,
    SetTextOp,
)

PAGE = """
<html><head><title>T</title><script>var x=1;</script></head>
<body>
  <header class="hdr"><h1 id="title">Old Title</h1></header>
  <main>
    <ul class="list">
      <li class="item">One</li>
      <li class="item">Two</li>
      <li class="item">Three</li>
      <li class="item">Four</li>
      <li class="item">Five</li>
    </ul>
    <a href="/old" class="cta">Click</a>
  </main>
</body></html>
"""


def _doc():
    return build_anchored_skeleton(PAGE, token_budget=50_000)


def test_skeleton_anchors_and_skips_script():
    doc = _doc()
    assert doc.truncated is False
    assert "@" in doc.skeleton
    # script body must not appear in the skeleton
    assert "var x=1" not in doc.skeleton
    # every element got an anchor in the soup
    assert all(ANCHOR_ATTR in t.attrs for t in doc.id_map.values())


def test_small_lists_not_collapsed():
    # 5 <li> is below the collapse threshold -> all shown, none hidden
    doc = _doc()
    assert "more <li>" not in doc.skeleton
    assert all(f">{w}<" or w in doc.skeleton for w in ["One", "Five"])


def test_large_sibling_run_collapses_under_budget_pressure():
    # Collapse is now budget-aware: with a TIGHT budget the pressure forces
    # a big run to fold (the real huge-page scenario).
    items = "".join(f"<li class='item'>Item {i}</li>" for i in range(2000))
    html = f"<html><body><ul>{items}</ul></body></html>"
    doc = build_anchored_skeleton(html, token_budget=1_000)
    assert "more <li>" in doc.skeleton
    assert doc.skeleton.count("@") < 2000


def test_free_budget_keeps_runs_expanded():
    # With plenty of budget, a 30-item run is shown in full (we no longer
    # flatten pages to nothing while the budget sits unused).
    items = "".join(f"<li class='item'>Item {i}</li>" for i in range(30))
    html = f"<html><body><ul>{items}</ul></body></html>"
    doc = build_anchored_skeleton(html, token_budget=50_000)
    assert "more <li>" not in doc.skeleton
    assert doc.skeleton.count("@li") == 0  # sanity: ids are numeric
    assert doc.skeleton.count("\n") >= 30


def test_relevance_keeps_prompt_target_visible_on_huge_run():
    # The element the user asked about is buried at index 900 of a 1500 run
    # that MUST collapse under a tight budget. Relevance biasing must keep it.
    rows = []
    for i in range(1500):
        if i == 900:
            rows.append('<div class="card"><button class="checkout-now">Buy</button></div>')
        else:
            rows.append(f'<div class="card"><span>item {i}</span></div>')
    html = f"<html><body><main>{''.join(rows)}</main></body></html>"
    doc = build_anchored_skeleton(
        html, token_budget=1_500, prompt="make the checkout-now button green"
    )
    assert "more <div>" in doc.skeleton  # it did collapse
    assert "checkout-now" in doc.skeleton  # ...but kept the relevant one


def test_big_page_uses_budget_not_flat():
    # Regression for "500k page costs same as 7k and does nothing": a large
    # page must produce a substantially bigger skeleton than a tiny one,
    # i.e. it actually spends the budget instead of collapsing to ~nothing.
    small = "<html><body><main><p>hello world</p></main></body></html>"
    big_rows = "".join(
        f'<section class="s{i}"><h2>Title {i}</h2>'
        f'<p>Paragraph body number {i} with distinct content.</p></section>'
        for i in range(4000)
    )
    big = f"<html><body><main>{big_rows}</main></body></html>"
    ds = build_anchored_skeleton(small, token_budget=40_000)
    db = build_anchored_skeleton(big, token_budget=40_000)
    assert db.stats["skeleton_tokens"] > ds.stats["skeleton_tokens"] * 20
    assert db.stats["skeleton_tokens"] > 5_000  # genuinely uses the budget


def test_unique_ids_never_collapse():
    items = "".join(f"<li id='row{i}'>Row {i}</li>" for i in range(30))
    html = f"<html><body><ul>{items}</ul></body></html>"
    doc = build_anchored_skeleton(html, token_budget=50_000)
    # distinct ids are individually addressable -> all kept, no collapse
    assert "more <li>" not in doc.skeleton
    assert "#row29" in doc.skeleton


def test_apply_patches_roundtrip():
    doc = _doc()

    # find anchor ids by content
    title_id = next(
        aid for aid, t in doc.id_map.items() if t.get("id") == "title"
    )
    cta_id = next(
        aid for aid, t in doc.id_map.items()
        if t.name == "a" and t.get("href") == "/old"
    )
    ul_id = next(
        aid for aid, t in doc.id_map.items() if t.name == "ul"
    )
    li_ids = [aid for aid, t in doc.id_map.items() if t.name == "li"]
    header_id = next(
        aid for aid, t in doc.id_map.items() if t.name == "header"
    )

    patches = [
        SetTextOp(target=title_id, text="New Title"),
        SetAttrOp(target=cta_id, name="href", value="/new"),
        AddClassOp(target=cta_id, class_name="primary"),
        SetStyleOp(target=cta_id, style="color:red"),
        DeleteOp(target=li_ids[0]),
        InsertOp(
            target=ul_id, html="<li class='item'>Inserted</li>",
            position="append",
        ),
        ReplaceInnerOp(target=header_id, html="<h1 id='title'>Replaced</h1>"),
        MoveOp(target=cta_id, to=ul_id, position="before"),
    ]

    html, applied, skipped = apply_patches(doc.soup, doc.id_map, patches)

    assert applied == len(patches)
    assert skipped == []
    assert "New Title" not in html  # header inner was replaced afterwards
    assert "Replaced" in html
    assert 'href="/new"' in html
    assert "primary" in html
    assert "color: red" in html
    assert "One" not in html  # first li deleted
    assert "Inserted" in html
    # anchors stripped from final output
    assert ANCHOR_ATTR not in html
    # untouched content preserved
    assert "Two" in html and "Five" in html


def test_inline_style_is_visible_in_skeleton():
    html = '<html><body><div style="color:red;padding:8px">x</div></body></html>'
    doc = build_anchored_skeleton(html, token_budget=50_000)
    assert "style=color:red;padding:8px" in doc.skeleton


def test_set_style_merges_not_overwrites():
    html = '<html><body><div style="color:red;padding:8px">x</div></body></html>'
    doc = build_anchored_skeleton(html, token_budget=50_000)
    div_id = next(a for a, t in doc.id_map.items() if t.name == "div")
    html_out, applied, skipped = apply_patches(
        doc.soup, doc.id_map,
        [SetStyleOp(target=div_id, style="color:blue;margin:4px")],
    )
    assert applied == 1 and skipped == []
    # overridden
    assert "color: blue" in html_out
    assert "color: red" not in html_out
    # untouched existing declaration preserved
    assert "padding: 8px" in html_out
    # new declaration added
    assert "margin: 4px" in html_out


def test_css_context_extracted():
    html = (
        '<html><head>'
        '<link rel="stylesheet" href="/app.css">'
        '<style>.btn{color:green}</style>'
        '</head><body><button class="btn">Go</button></body></html>'
    )
    doc = build_anchored_skeleton(html, token_budget=50_000)
    assert "/app.css" in doc.css_context
    assert ".btn{color:green}" in doc.css_context
    assert doc.stats["css_tokens"] > 0


JS_PAGE = """<html><head>
<style>:root{--bg:#09090b;--accent:#fff} section{opacity:0} section.visible{opacity:1}</style>
<script>
// init scroll reveal
const obs = new IntersectionObserver(e => e.forEach(x => x.target.classList.add("visible")));
document.querySelectorAll("section").forEach(s => obs.observe(s));
</script>
</head><body>
<section id="a"><p>Important content paragraph one.</p></section>
<section id="b"><p>Important content paragraph two.</p></section>
</body></html>"""


def test_scripts_and_styles_survive_preprocess():
    # Regression: whitespace-collapse used to merge JS onto one line, so a
    # // comment swallowed the whole script and the page lost its behavior.
    doc = build_anchored_skeleton(JS_PAGE, token_budget=50_000)
    out, _, _ = apply_patches(doc.soup, doc.id_map, [])
    assert "IntersectionObserver" in out
    # the line after the // comment must still be on its own line
    assert "\n" in out[out.find("<script") : out.find("</script>")]
    assert "querySelectorAll" in out
    assert "section.visible{opacity:1}" in out
    assert "Important content paragraph one." in out
    assert "Important content paragraph two." in out


def test_set_css_var_themes_without_touching_style():
    doc = build_anchored_skeleton(JS_PAGE, token_budget=50_000)
    out, applied, skipped = apply_patches(
        doc.soup, doc.id_map,
        [
            SetCssVarOp(name="--bg", value="#1a0b14"),
            SetCssVarOp(name="accent", value="#ff4fa3"),  # no -- prefix
        ],
    )
    assert applied == 2 and skipped == []
    assert 'id="prism-overrides"' in out
    assert "--bg:#1a0b14 !important" in out
    assert "--accent:#ff4fa3 !important" in out
    # original stylesheet untouched
    assert ":root{--bg:#09090b;--accent:#fff}" in out


def test_destructive_ops_on_protected_tags_refused():
    doc = build_anchored_skeleton(JS_PAGE, token_budget=50_000)
    style_id = next(a for a, t in doc.id_map.items() if t.name == "style")
    body_id = next(a for a, t in doc.id_map.items() if t.name == "body")
    out, applied, skipped = apply_patches(
        doc.soup, doc.id_map,
        [
            ReplaceInnerOp(target=style_id, html=":root{}"),
            DeleteOp(target=body_id),
        ],
    )
    assert applied == 0
    assert len(skipped) == 2
    assert all("protected" in s for s in skipped)
    # nothing was destroyed
    assert "IntersectionObserver" in out
    assert "Important content paragraph one." in out


def test_compact_profile_shrinks_but_keeps_id_map():
    from app.preprocessing.anchor_skeleton import (
        COMPACT_PROFILE,
        VERBOSE_PROFILE,
    )

    card = (
        '<div class="flex flex-col gap-4 rounded-xl border border-zinc-800 '
        'bg-zinc-900 p-6 shadow hover:shadow-lg transition">'
        '<p class="desc">A fairly long description of this card that goes on '
        'for a while to exercise text truncation limits.</p></div>'
    )
    html = f"<html><body><main>{''.join(card for _ in range(8))}</main></body></html>"

    v = build_anchored_skeleton(html, 60_000, profile=VERBOSE_PROFILE)
    c = build_anchored_skeleton(html, 60_000, profile=COMPACT_PROFILE)

    # Compression is real...
    assert c.stats["skeleton_tokens"] < v.stats["skeleton_tokens"] * 0.7
    # ...but the apply contract (anchor ids -> elements) is untouched.
    assert list(v.id_map) == list(c.id_map)
    assert v.stats["element_count"] == c.stats["element_count"]


def test_rollback_env_restores_verbose(monkeypatch):
    from app.config import settings
    from app.preprocessing.anchor_skeleton import VERBOSE_PROFILE

    html = '<html><body><div class="a b c d e f g h i j k l m">x</div></body></html>'
    monkeypatch.setattr(settings, "dom_skeleton_compact", False)
    got = build_anchored_skeleton(html, 60_000)  # resolves profile from settings
    expected = build_anchored_skeleton(html, 60_000, profile=VERBOSE_PROFILE)
    assert got.skeleton == expected.skeleton  # exact prior behavior


def test_add_css_rule_parses_and_routes_to_css_rules():
    import asyncio

    from app.handlers.dom_manipulation import DOMManipulationHandler
    from app.schemas.dom_manipulation import (
        DOMManipulationRequest,
        DOMPatchResult,
    )

    # Parses through the patch-op union.
    parsed = DOMPatchResult.model_validate(
        {
            "patches": [
                {"op": "add_css_rule",
                 "css": "ytd-thumbnail,img{border-radius:50%!important}"}
            ],
            "changes_summary": "round thumbnails",
        }
    )
    assert parsed.patches[0].op == "add_css_rule"

    h = DOMManipulationHandler()
    html = "<html><body><main><img class='t' src='a.jpg'></main></body></html>"
    req = DOMManipulationRequest(
        page_url="https://www.youtube.com/", html=html,
        user_prompt="make the thumbnails round",
    )
    ctx = asyncio.run(h.preprocess(html, req))
    res = asyncio.run(h.postprocess(parsed, ctx))

    assert res.css_rules == ["ytd-thumbnail,img{border-radius:50%!important}"]
    assert res.patches == [] and res.css_vars == {}
    # response stays tiny (no server-html bloat)
    assert res.modified_html == ""


def test_bad_target_is_skipped_not_fatal():
    doc = _doc()
    html, applied, skipped = apply_patches(
        doc.soup,
        doc.id_map,
        [SetTextOp(target="999999", text="nope")],
    )
    assert applied == 0
    assert len(skipped) == 1
    assert "not found" in skipped[0]


def test_large_feed_collapses_within_budget():
    rows = "".join(
        f'<div class="r"><a href="/v/{i}">vid {i}</a></div>' for i in range(5000)
    )
    big = f"<html><body><main>{rows}</main></body></html>"
    doc = build_anchored_skeleton(big, token_budget=20_000)
    # 5000 near-identical rows must collapse, not blow the budget
    assert doc.truncated is False
    assert "more <div>" in doc.skeleton
    assert doc.stats["skeleton_tokens"] <= 20_000
