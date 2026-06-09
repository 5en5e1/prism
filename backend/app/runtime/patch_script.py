"""Generate the self-contained in-browser patch runtime.

The backend returns the original HTML *verbatim* with one ``<script>``
appended. That script applies the edits to the live, post-JS DOM and keeps
re-asserting them through SPA re-renders / animations. Because we never parse
or reserialize the document, fidelity is exact for any site (static, dynamic,
animated, framework-driven).

Design notes:
- Visual/text ops (set_text/attr/style/class, css vars, replace_inner) are
  idempotent and re-asserted on every pass, so they survive framework
  re-renders.
- Structural ops (insert/replace_element/move) tag their output with a
  one-time marker so re-application never duplicates; if a framework wipes
  the marked node, it is recreated.
- ``delete`` is naturally idempotent and stays deleted across re-renders.
- Destructive ops on html/head/body/script/style are refused client-side
  too (defense in depth).
- A MutationObserver (disconnected during our own writes) re-applies with a
  debounce; an internal guard prevents loops.
"""
import json

# The runtime. ``__PAYLOAD__`` is replaced with a JSON object:
# {"ops":[...], "cssVars":{...}}.
_RUNTIME = r"""
(function(){
  "use strict";
  var P = __PAYLOAD__;
  if (!P || (!(P.ops && P.ops.length) && !(P.cssVars && Object.keys(P.cssVars).length))) return;
  var PROT = {HTML:1, HEAD:1, BODY:1, SCRIPT:1, STYLE:1};
  var DESTR = {replace_inner:1, replace_element:1, "delete":1, set_text:1};
  var applying = false, mo = null, t = null;

  function q(sel){ try { return document.querySelector(sel); } catch(e){ return null; } }

  function resolve(op){
    var el = op.s ? q(op.s) : null;
    if (el) return el;
    var h = op.h; if (!h) return null;
    var list = document.getElementsByTagName(h.tag || "*"), probe = (h.text||"").slice(0,40);
    for (var i=0;i<list.length;i++){
      var c = list[i], ok = true;
      if (probe && (c.textContent||"").indexOf(probe) === -1) ok = false;
      if (ok && h.attrs){ for (var k in h.attrs){ if (c.getAttribute(k) !== h.attrs[k]){ ok=false; break; } } }
      if (ok) return c;
    }
    return null;
  }

  function parseDecls(s){ var o={}; (s||"").split(";").forEach(function(p){
    var i=p.indexOf(":"); if(i>0){ var k=p.slice(0,i).trim().toLowerCase(); if(k) o[k]=p.slice(i+1).trim(); }}); return o; }
  function mergeStyle(el, css){
    var cur=parseDecls(el.getAttribute("style")||""), inc=parseDecls(css), out=[];
    for (var k in cur) out.push([k,cur[k]]);
    for (var k2 in inc){ var f=false; for (var j=0;j<out.length;j++){ if(out[j][0]===k2){ out[j][1]=inc[k2]; f=true; break; } } if(!f) out.push([k2,inc[k2]]); }
    el.setAttribute("style", out.map(function(p){return p[0]+": "+p[1];}).join("; ") + (out.length?";":""));
  }
  function frag(html){ var tpl=document.createElement("template"); tpl.innerHTML=html; return tpl.content; }
  function mark(node, id){ if(node && node.setAttribute) node.setAttribute("data-prism-op", id); }
  function done(id){ return !!document.querySelector('[data-prism-op="'+id+'"]'); }

  function applyOp(op){
    if (op.op === "set_css_var") return;
    var el = resolve(op);
    if (!el) return;
    if (DESTR[op.op] && PROT[el.tagName]) return;        // protected
    switch (op.op){
      case "set_text": el.textContent = op.text; break;
      case "set_attr":
        if (op.value === null) el.removeAttribute(op.name); else el.setAttribute(op.name, op.value); break;
      case "set_style": mergeStyle(el, op.style); break;
      case "add_class": el.classList.add(op.class_name); break;
      case "remove_class": el.classList.remove(op.class_name); break;
      case "replace_inner": el.innerHTML = op.html; break;
      case "delete": el.parentNode && el.parentNode.removeChild(el); break;
      case "replace_element": {
        if (done(op.id)) break;
        var f = frag(op.html), first = f.firstElementChild;
        mark(first, op.id);
        el.parentNode && el.parentNode.replaceChild(f, el);
        break;
      }
      case "insert": {
        if (done(op.id)) break;
        var fr = frag(op.html); mark(fr.firstElementChild, op.id);
        if (op.position === "before") el.parentNode.insertBefore(fr, el);
        else if (op.position === "after") el.parentNode.insertBefore(fr, el.nextSibling);
        else if (op.position === "prepend") el.insertBefore(fr, el.firstChild);
        else el.appendChild(fr);
        break;
      }
      case "move": {
        if (done(op.id)) break;
        var dest = op.t ? q(op.t) : null; if (!dest) break;
        mark(el, op.id);
        if (op.position === "before") dest.parentNode.insertBefore(el, dest);
        else if (op.position === "after") dest.parentNode.insertBefore(el, dest.nextSibling);
        else if (op.position === "prepend") dest.insertBefore(el, dest.firstChild);
        else dest.appendChild(el);
        break;
      }
    }
  }

  function ensureVars(){
    var v = P.cssVars || {}, keys = Object.keys(v); if (!keys.length) return;
    var s = document.getElementById("prism-overrides");
    if (!s){ s = document.createElement("style"); s.id = "prism-overrides";
      (document.head || document.documentElement).appendChild(s); }
    var d = keys.map(function(k){ var n = k.indexOf("--")===0 ? k : "--"+k; return n+":"+v[k]+" !important;"; }).join("");
    var css = ":root{"+d+"}";
    if (s.textContent !== css) s.textContent = css;
  }

  function applyAll(){
    if (applying) return; applying = true;
    if (mo) mo.disconnect();
    try { ensureVars(); for (var i=0;i<(P.ops||[]).length;i++){ try { applyOp(P.ops[i]); } catch(e){} } }
    finally {
      applying = false;
      if (mo) try { mo.observe(document.documentElement, {childList:true, subtree:true, attributes:true}); } catch(e){}
    }
  }

  function schedule(){ if (applying) return; clearTimeout(t); t = setTimeout(applyAll, 80); }

  applyAll();
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", applyAll);
  try {
    mo = new MutationObserver(schedule);
    mo.observe(document.documentElement, {childList:true, subtree:true, attributes:true});
  } catch(e){}
})();
"""


def build_patch_script(ops: list[dict], css_vars: dict[str, str]) -> str:
    """Return a ``<script>...</script>`` string applying ``ops``/``css_vars``.

    The payload is embedded as JSON (not interpolated into code), and any
    ``</script>`` inside string data is neutralized so it cannot break out
    of the tag.
    """
    payload = json.dumps(
        {"ops": ops, "cssVars": css_vars},
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    body = _RUNTIME.replace("__PAYLOAD__", payload)
    return f'<script id="prism-patch" data-prism-runtime="1">{body}</script>'


def inject_script(html: str, script: str) -> str:
    """Append ``script`` to ``html`` without otherwise touching a byte.

    Insert just before </body> (then </html>, else append) using a
    case-insensitive search on the original string â€” no parsing/reserializing.
    """
    for close in ("</body>", "</BODY>", "</html>", "</HTML>"):
        idx = html.rfind(close)
        if idx != -1:
            return html[:idx] + script + html[idx:]
    return html + script
