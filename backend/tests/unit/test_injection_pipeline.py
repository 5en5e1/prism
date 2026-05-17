"""Tests for live-DOM injection mode (default).

Verifies the core guarantee: original HTML is returned byte-for-byte with a
single runtime <script> appended, selectors resolve uniquely against the real
CSS engine, and the generated JS is syntactically valid (node --check).
"""
import json
import re
import shutil
import subprocess
import tempfile

import pytest
from bs4 import BeautifulSoup

from app.preprocessing.anchor_skeleton import build_anchored_skeleton
from app.preprocessing.selector import (
    compute_unique_ids,
    robust_selector,
)
from app.runtime.patch_script import build_patch_script, inject_script

REAL_PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<style>:root{--bg:#09090b;--accent:#fff}
section{opacity:0;transition:opacity .6s}section.visible{opacity:1}</style>
<script>
// scroll reveal - newline-sensitive, must survive verbatim
const obs = new IntersectionObserver(e => e.forEach(x => {
  if (x.isIntersecting) x.target.classList.add("visible");
}));
document.querySelectorAll("section").forEach(s => obs.observe(s));
</script>
</head><body style="--x:1">
<nav class="nav"><div class="nav-logo">&lt;matei /&gt;</div></nav>
<section class="hero visible" id="about">
  <div class="avatar" id="av"><img alt="me" src="pf.png"></div>
  <p class="hero-desc">A long important paragraph that must survive intact.</p>
</section>
<section id="stack"><h2>Tech Stack</h2>
  <span class="chip">Python</span><span class="chip">C++</span></section>
<footer><p>Designed by Farcas Antonio Matei 2026</p></footer>
</body></html>"""


def test_original_html_preserved_verbatim():
    script = build_patch_script(
        [{"id": "p0", "op": "set_text", "s": "#av", "h": {"tag": "div"}, "text": "x"}],
        {"--bg": "#1a0b14"},
    )
    out = inject_script(REAL_PAGE, script)
    cut = REAL_PAGE.rfind("</body>")
    # original is reproduced exactly, with the script spliced in before </body>
    assert out == REAL_PAGE[:cut] + script + REAL_PAGE[cut:]
    assert out.endswith("</body></html>")
    assert script in out
    # the snapshot regions that used to get corrupted are all intact
    assert "IntersectionObserver" in out
    assert "\n  if (x.isIntersecting)" in out  # JS newlines preserved
    assert ":root{--bg:#09090b;--accent:#fff}" in out
    assert "A long important paragraph that must survive intact." in out
    assert "Designed by Farcas Antonio Matei 2026" in out
    # exactly one byte-region added
    assert len(out) == len(REAL_PAGE) + len(script)


def test_selectors_resolve_uniquely_with_real_css_engine():
    doc = build_anchored_skeleton(REAL_PAGE, token_budget=50_000)
    uids = compute_unique_ids(doc.soup)
    # soupsieve == real CSS selector engine; proxy for browser querySelector
    for aid, tag in doc.id_map.items():
        sel = robust_selector(tag, uids)
        found = doc.soup.select(sel)
        assert len(found) == 1, f"{sel!r} matched {len(found)}"
        assert found[0] is tag, f"{sel!r} resolved to wrong element"


def test_generated_script_is_valid_js():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    script = build_patch_script(
        [
            {"id": "p0", "op": "set_text", "s": "#av", "h": {"tag": "div"},
             "text": "</script><script>alert(1)"},  # injection attempt
            {"id": "p1", "op": "insert", "s": "#stack", "h": {"tag": "section"},
             "html": "<span>new</span>", "position": "append"},
            {"id": "p2", "op": "move", "s": "#av", "t": "footer",
             "h": {"tag": "div"}, "position": "append"},
        ],
        {"--bg": "#000", "accent": "#ff4fa3"},
    )
    body = re.sub(r"^<script[^>]*>|</script>$", "", script)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(body)
        path = f.name
    res = subprocess.run([node, "--check", path], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    # the </script> inside string data must have been neutralized
    assert "<\\/script>" in script
    assert "</script><script>alert(1)" not in body


def test_payload_carries_ops_and_css_vars():
    script = build_patch_script(
        [{"id": "p0", "op": "set_attr", "s": "#av", "h": {"tag": "div"},
          "name": "href", "value": None}],
        {"--bg": "#1a0b14"},
    )
    raw = re.sub(r"^<script[^>]*>|</script>$", "", script)
    m = re.search(r'var P = (\{.*?\});\s*\n', raw, re.DOTALL)
    assert m, "payload not found"
    payload = json.loads(m.group(1))
    assert payload["cssVars"] == {"--bg": "#1a0b14"}
    assert payload["ops"][0]["op"] == "set_attr"
    assert payload["ops"][0]["value"] is None


def test_inject_without_body_appends():
    frag = "<div>no body or html here</div>"
    out = inject_script(frag, "<script>1</script>")
    assert out == frag + "<script>1</script>"
