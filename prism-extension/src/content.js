(function bootPrism() {
  if (window.__prismExtensionLoaded) {
    return;
  }

  window.__prismExtensionLoaded = true;

  const HTML_CACHE_KEY = "domHtmlCache";
  const MAX_CAPTURED_HTML_CHARS = 2_000_000;
  const CHARS_PER_TOKEN = 4;
  const MAX_CACHED_PAGES = 20;

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "CAPTURE_PAGE_HTML") {
      handleCapturePageHtml()
        .then(sendResponse)
        .catch((error) => sendResponse({ error: error.message }));
      return true;
    }

    if (message?.type === "APPLY_PATCHES") {
      handleApplyPatches(message)
        .then(sendResponse)
        .catch((error) => sendResponse({ error: error.message }));
      return true;
    }

    if (message?.type === "CLEAR_PAGE_CACHE") {
      clearPageCache()
        .then(sendResponse)
        .catch((error) => sendResponse({ error: error.message }));
      return true;
    }

    if (message?.type === "PING_CONTENT_SCRIPT") {
      sendResponse({ ok: true });
      return true;
    }

    return false;
  });

  (async () => {
    const { settings = { enabled: true } } = await chrome.storage.local.get("settings");

    if (!settings.enabled) {
      return;
    }

    await applyCachedPatches();
    chrome.runtime.sendMessage({ type: "PING_EXTENSION" });
  })();

  function getPageKey(url = window.location.href) {
    const parsedUrl = new URL(url);
    return `${parsedUrl.origin}${parsedUrl.pathname}`;
  }

  function estimateTokens(text) {
    return Math.ceil((text ? text.length : 0) / CHARS_PER_TOKEN);
  }

  // Capture the LIVE, post-JS DOM with full fidelity. We clone so the live
  // page is untouched, but we deliberately keep <script>/<style>/<iframe>
  // intact: stripping them used to destroy JS-driven pages, and the backend
  // already compresses to a skeleton for the model.
  function createSnapshotHtml() {
    const clone = document.documentElement.cloneNode(true);
    let html = `<!doctype html>\n${clone.outerHTML}`;
    let truncated = false;

    if (html.length > MAX_CAPTURED_HTML_CHARS) {
      html = html.slice(0, MAX_CAPTURED_HTML_CHARS);
      truncated = true;
    }

    const elementCount = clone.querySelectorAll("body, body *").length;
    return { html, elementCount, truncated };
  }

  async function handleCapturePageHtml() {
    const snapshot = createSnapshotHtml();
    return {
      ...snapshot,
      estimatedTokens: estimateTokens(snapshot.html),
      pageUrl: window.location.href,
      pageKey: getPageKey()
    };
  }

  // ---- Live-DOM patch applier -------------------------------------------
  // Mutates the real document in place (never replaces it), so existing
  // scripts, event listeners, framework state and animations all survive.

  const PROTECTED = { HTML: 1, HEAD: 1, BODY: 1, SCRIPT: 1, STYLE: 1 };
  const DESTRUCTIVE = {
    replace_inner: 1,
    replace_element: 1,
    delete: 1,
    set_text: 1
  };

  function resolveTarget(op) {
    let el = null;
    if (op.s) {
      try {
        el = document.querySelector(op.s);
      } catch (_e) {
        el = null;
      }
    }
    if (el) return el;

    const hint = op.h;
    if (!hint) return null;
    const list = document.getElementsByTagName(hint.tag || "*");
    const probe = (hint.text || "").slice(0, 40);
    for (let i = 0; i < list.length; i += 1) {
      const c = list[i];
      let ok = true;
      if (probe && (c.textContent || "").indexOf(probe) === -1) ok = false;
      if (ok && hint.attrs) {
        for (const k in hint.attrs) {
          if (c.getAttribute(k) !== hint.attrs[k]) {
            ok = false;
            break;
          }
        }
      }
      if (ok) return c;
    }
    return null;
  }

  function parseDecls(styleText) {
    const out = {};
    (styleText || "").split(";").forEach((part) => {
      const i = part.indexOf(":");
      if (i > 0) {
        const k = part.slice(0, i).trim().toLowerCase();
        if (k) out[k] = part.slice(i + 1).trim();
      }
    });
    return out;
  }

  function mergeStyle(el, css) {
    const cur = parseDecls(el.getAttribute("style") || "");
    const inc = parseDecls(css);
    Object.keys(inc).forEach((k) => {
      cur[k] = inc[k];
    });
    const text = Object.keys(cur)
      .map((k) => `${k}: ${cur[k]}`)
      .join("; ");
    el.setAttribute("style", text + (text ? ";" : ""));
  }

  function fragment(htmlStr) {
    const tpl = document.createElement("template");
    tpl.innerHTML = htmlStr;
    return tpl.content;
  }

  function marked(opId) {
    return !!document.querySelector(`[data-prism-op="${opId}"]`);
  }

  function applyOp(op) {
    if (op.op === "set_css_var") return;
    const el = resolveTarget(op);
    if (!el) return;
    if (DESTRUCTIVE[op.op] && PROTECTED[el.tagName]) return;

    switch (op.op) {
      case "set_text":
        el.textContent = op.text;
        break;
      case "set_attr":
        if (op.value === null) el.removeAttribute(op.name);
        else el.setAttribute(op.name, op.value);
        break;
      case "set_style":
        mergeStyle(el, op.style);
        break;
      case "add_class":
        el.classList.add(op.class_name);
        break;
      case "remove_class":
        el.classList.remove(op.class_name);
        break;
      case "replace_inner":
        el.innerHTML = op.html;
        break;
      case "delete":
        if (el.parentNode) el.parentNode.removeChild(el);
        break;
      case "replace_element": {
        if (marked(op.id)) break;
        const f = fragment(op.html);
        if (f.firstElementChild) f.firstElementChild.setAttribute("data-prism-op", op.id);
        if (el.parentNode) el.parentNode.replaceChild(f, el);
        break;
      }
      case "insert": {
        if (marked(op.id)) break;
        const f = fragment(op.html);
        if (f.firstElementChild) f.firstElementChild.setAttribute("data-prism-op", op.id);
        if (op.position === "before") el.parentNode.insertBefore(f, el);
        else if (op.position === "after") el.parentNode.insertBefore(f, el.nextSibling);
        else if (op.position === "prepend") el.insertBefore(f, el.firstChild);
        else el.appendChild(f);
        break;
      }
      case "move": {
        if (marked(op.id)) break;
        let dest = null;
        try {
          dest = op.t ? document.querySelector(op.t) : null;
        } catch (_e) {
          dest = null;
        }
        if (!dest) break;
        el.setAttribute("data-prism-op", op.id);
        if (op.position === "before") dest.parentNode.insertBefore(el, dest);
        else if (op.position === "after") dest.parentNode.insertBefore(el, dest.nextSibling);
        else if (op.position === "prepend") dest.insertBefore(el, dest.firstChild);
        else dest.appendChild(el);
        break;
      }
      default:
        break;
    }
  }

  // Single managed stylesheet holds both CSS variable overrides and
  // injected site-wide rules. Last-in-<head> + !important beats author CSS,
  // and a selector-based rule covers virtualized/future elements (feeds,
  // SPA re-render) that per-element ops cannot.
  function ensureOverrides(cssVars, cssRules) {
    const keys = Object.keys(cssVars || {});
    const rules = Array.isArray(cssRules) ? cssRules : [];
    if (!keys.length && !rules.length) return;
    let style = document.getElementById("prism-overrides");
    if (!style) {
      style = document.createElement("style");
      style.id = "prism-overrides";
      (document.head || document.documentElement).appendChild(style);
    }
    let css = "";
    if (keys.length) {
      const decls = keys
        .map((k) => {
          const name = k.indexOf("--") === 0 ? k : `--${k}`;
          return `${name}:${cssVars[k]} !important;`;
        })
        .join("");
      css += `:root{${decls}}\n`;
    }
    css += rules.join("\n");
    if (style.textContent !== css) style.textContent = css;
    // Keep it the last <head> child so it wins specificity ties even if the
    // page injects its own styles later.
    const head = document.head;
    if (head && style.parentNode === head && head.lastElementChild !== style) {
      head.appendChild(style);
    }
  }

  let patchState = { patches: [], cssVars: {}, cssRules: [] };
  let applying = false;
  let observer = null;
  let debounceTimer = null;

  function applyAll() {
    if (applying) return;
    applying = true;
    if (observer) observer.disconnect();
    try {
      ensureOverrides(patchState.cssVars, patchState.cssRules);
      (patchState.patches || []).forEach((op) => {
        try {
          applyOp(op);
        } catch (_e) {
          /* one bad patch must not stop the rest */
        }
      });
    } finally {
      applying = false;
      if (observer) {
        try {
          observer.observe(document.documentElement, {
            childList: true,
            subtree: true,
            attributes: true
          });
        } catch (_e) {
          /* document not ready yet */
        }
      }
    }
  }

  function scheduleApply() {
    if (applying) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(applyAll, 80);
  }

  function startPersistence() {
    if (observer) return;
    observer = new MutationObserver(scheduleApply);
    applyAll();
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", applyAll);
    }
  }

  function setActivePatches(patches, cssVars, cssRules) {
    patchState = {
      patches: Array.isArray(patches) ? patches : [],
      cssVars: cssVars || {},
      cssRules: Array.isArray(cssRules) ? cssRules : []
    };
    startPersistence();
    applyAll();
  }

  function applyModifiedHtml(modifiedHtml) {
    if (!modifiedHtml || typeof modifiedHtml !== "string") {
      return false;
    }

    const parsed = new DOMParser().parseFromString(modifiedHtml, "text/html");
    const nextHtml = parsed.documentElement;
    const nextHead = parsed.head;
    const nextBody = parsed.body;

    if (!nextBody) {
      return false;
    }

    Array.from(document.documentElement.attributes).forEach((attr) => {
      document.documentElement.removeAttribute(attr.name);
    });
    Array.from(nextHtml.attributes).forEach((attr) => {
      document.documentElement.setAttribute(attr.name, attr.value);
    });

    if (document.head && nextHead) {
      document.head.innerHTML = nextHead.innerHTML;
    }

    document.body.innerHTML = nextBody.innerHTML;
    return true;
  }

  async function handleApplyPatches(message) {
    if (message.modifiedHtml) {
      applyModifiedHtml(message.modifiedHtml);
    } else {
      setActivePatches(message.patches, message.cssVars, message.cssRules);
    }

    if (!message.cache) {
      return { ok: true, cached: false };
    }

    try {
      await savePageCache({
        pageKey: message.pageKey || getPageKey(),
        patches: message.patches || [],
        cssVars: message.cssVars || {},
        cssRules: message.cssRules || [],
        modifiedHtml: message.modifiedHtml || "",
        sourcePrompt: message.sourcePrompt || "",
        changesSummary: message.changesSummary || "",
        traceId: message.traceId || "",
        pageUrl: window.location.href
      });
      return { ok: true, cached: true };
    } catch (error) {
      return { ok: true, cached: false, cacheError: error.message };
    }
  }

  async function getHtmlCache() {
    const data = await chrome.storage.local.get(HTML_CACHE_KEY);
    return data[HTML_CACHE_KEY] || {};
  }

  function evictOldestEntries(cache, maxEntries) {
    const keys = Object.keys(cache);
    if (keys.length <= maxEntries) {
      return cache;
    }
    const orderedKeys = keys.sort(
      (a, b) => (cache[a]?.updatedAt || "").localeCompare(cache[b]?.updatedAt || "")
    );
    const trimmed = { ...cache };
    orderedKeys.slice(0, keys.length - maxEntries).forEach((key) => {
      delete trimmed[key];
    });
    return trimmed;
  }

  async function savePageCache(entry) {
    const cache = await getHtmlCache();
    cache[entry.pageKey] = {
      patches: entry.patches,
      cssVars: entry.cssVars,
      cssRules: entry.cssRules || [],
      modifiedHtml: entry.modifiedHtml || "",
      sourcePrompt: entry.sourcePrompt,
      changesSummary: entry.changesSummary,
      traceId: entry.traceId,
      pageUrl: entry.pageUrl,
      updatedAt: new Date().toISOString()
    };
    const bounded = evictOldestEntries(cache, MAX_CACHED_PAGES);
    await chrome.storage.local.set({ [HTML_CACHE_KEY]: bounded });
  }

  async function clearPageCache() {
    const pageKey = getPageKey();
    const cache = await getHtmlCache();
    delete cache[pageKey];
    await chrome.storage.local.set({ [HTML_CACHE_KEY]: cache });
    return { ok: true, pageKey };
  }

  async function applyCachedPatches() {
    const cache = await getHtmlCache();
    const pageEntry = cache[getPageKey()];
    if (
      !pageEntry ||
      (!pageEntry.modifiedHtml &&
        !pageEntry.patches?.length &&
        !Object.keys(pageEntry.cssVars || {}).length &&
        !(pageEntry.cssRules || []).length)
    ) {
      return;
    }
    try {
      if (pageEntry.modifiedHtml) {
        applyModifiedHtml(pageEntry.modifiedHtml);
        return;
      }

      setActivePatches(pageEntry.patches, pageEntry.cssVars, pageEntry.cssRules);
    } catch (_error) {
      // A stale cache entry should never break the live page.
    }
  }
})();
