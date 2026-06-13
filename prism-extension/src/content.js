(function bootExtension() {
  if (window.__prismExtensionLoaded) {
    return;
  }

  window.__prismExtensionLoaded = true;

  const HTML_CACHE_KEY = "domHtmlCache";
  const MAX_CAPTURED_HTML_CHARS = 2_000_000;
  const CHARS_PER_TOKEN = 4;
  const MAX_CACHED_PAGES = 20;
  const NAVIGATION_POLL_MS = 500;
  const TRACKING_QUERY_NAMES = new Set(["fbclid", "gclid", "msclkid"]);
  let browserSession = createBrowserSessionState();

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

    if (message?.type === "START_ELEMENT_SELECTION") {
      startElementSelection(message.reference, message.selectedElements || []);
      sendResponse({ ok: true });
      return true;
    }

    if (message?.type === "CANCEL_ELEMENT_SELECTION") {
      stopElementSelection({ hideMarkers: true });
      sendResponse({ ok: true });
      return true;
    }

    if (message?.type === "UPDATE_ELEMENT_SELECTION") {
      updateElementSelection(message.reference, message.selectedElements || [], message.markersVisible);
      sendResponse({ ok: true });
      return true;
    }

    if (message?.type === "FORGET_SELECTED_ELEMENT") {
      forgetSelectedElement(message.reference);
      sendResponse({ ok: true });
      return true;
    }

    if (message?.type === "CLEAR_SELECTED_ELEMENTS") {
      clearSelectedElementMarkers();
      sendResponse({ ok: true });
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

  function stableHash(input) {
    let hash = 2166136261;
    const text = String(input || "");
    for (let i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function semanticQuery(search) {
    const params = new URLSearchParams(search || "");
    const kept = [];
    params.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (TRACKING_QUERY_NAMES.has(lower) || lower.startsWith("utm_")) {
        return;
      }
      kept.push([key, value]);
    });
    kept.sort((a, b) => `${a[0]}=${a[1]}`.localeCompare(`${b[0]}=${b[1]}`));
    return new URLSearchParams(kept).toString();
  }

  function routeHash(hash) {
    const value = (hash || "").replace(/^#/, "");
    return value.startsWith("/") || value.startsWith("!") ? value : "";
  }

  function getPageIdentity(url = window.location.href) {
    const parsedUrl = new URL(url);
    const query = semanticQuery(parsedUrl.search);
    const hashRoute = routeHash(parsedUrl.hash);
    let routeKey = parsedUrl.pathname || "/";
    if (query) routeKey += `?${query}`;
    if (hashRoute) routeKey += `#${hashRoute}`;
    const canonicalUrl = `${parsedUrl.origin}${routeKey}`;
    const viewportVariant = `${window.innerWidth}x${window.innerHeight}@${window.devicePixelRatio || 1}`;
    const authVariant = document.cookie ? "possibly-authenticated" : "unknown";
    const websiteId = stableHash(parsedUrl.origin);
    const pageId = stableHash(`${parsedUrl.origin}|${routeKey}|${viewportVariant}|${authVariant}`);
    return {
      pageId,
      websiteId,
      origin: parsedUrl.origin,
      path: parsedUrl.pathname || "/",
      routeKey,
      canonicalUrl,
      queryPolicy: "semantic",
      hashPolicy: "route-only",
      viewportVariant,
      authVariant
    };
  }

  function getPageKey(url = window.location.href) {
    return getPageIdentity(url).canonicalUrl;
  }

  function createBrowserSessionState() {
    const identity = getPageIdentity();
    return {
      currentUrl: window.location.href,
      pageKey: identity.canonicalUrl,
      routeKey: identity.routeKey,
      navigationEpoch: 1,
      liveDomValid: true
    };
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

  function collectElementSummary(limit = 250) {
    const elements = [];
    const nodes = document.querySelectorAll("body, body *");
    for (let i = 0; i < nodes.length && elements.length < limit; i += 1) {
      const el = nodes[i];
      const rect = el.getBoundingClientRect();
      if (!rect.width && !rect.height) continue;
      const style = window.getComputedStyle(el);
      elements.push({
        tag: el.tagName.toLowerCase(),
        id: el.id || "",
        className: typeof el.className === "string" ? el.className.slice(0, 120) : "",
        role: el.getAttribute("role") || "",
        ariaLabel: el.getAttribute("aria-label") || "",
        text: (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120),
        visible: style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity) !== 0,
        rect: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        },
        computed: {
          display: style.display,
          position: style.position,
          color: style.color,
          backgroundColor: style.backgroundColor,
          fontSize: style.fontSize
        }
      });
    }
    return elements;
  }

  function detectFrameworkMarkers() {
    const root = document.documentElement;
    return {
      react: Boolean(document.querySelector("[data-reactroot], [data-reactid], #__next")),
      vue: Boolean(document.querySelector("[data-v-app], [data-server-rendered]")),
      astro: Boolean(document.querySelector("[data-astro-cid]")),
      shopify: /Shopify/i.test(root.innerHTML.slice(0, 200000)),
      wordpress: Boolean(document.querySelector('meta[name="generator"][content*="WordPress" i], body[class*="wp-"]'))
    };
  }

  function createPageSnapshotMetadata(snapshot) {
    return {
      pageUrl: window.location.href,
      pageIdentity: getPageIdentity(),
      navigationEpoch: browserSession.navigationEpoch,
      capturedAt: new Date().toISOString(),
      title: document.title || "",
      elementCount: snapshot.elementCount,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio || 1,
        scrollX: window.scrollX,
        scrollY: window.scrollY
      },
      sources: [
        "live_dom",
        "computed_styles_layout",
        "accessibility_semantics",
        "visual_viewport",
        "raw_html_archive"
      ],
      frameworkMarkers: detectFrameworkMarkers(),
      elementSummary: collectElementSummary()
    };
  }

  async function handleCapturePageHtml() {
    const snapshot = createSnapshotHtml();
    const pageIdentity = getPageIdentity();
    return {
      ...snapshot,
      estimatedTokens: estimateTokens(snapshot.html),
      pageUrl: window.location.href,
      pageKey: pageIdentity.canonicalUrl,
      pageIdentity,
      pageSnapshot: createPageSnapshotMetadata(snapshot)
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

  let patchState = { patches: [], cssVars: {}, cssRules: [], pageKey: getPageKey(), navigationEpoch: 0 };
  let applying = false;
  let observer = null;
  let debounceTimer = null;

  function applyAll() {
    if (applying) return;
    if (patchState.pageKey && patchState.pageKey !== getPageKey()) {
      handleNavigationMaybe();
      if (patchState.pageKey && patchState.pageKey !== getPageKey()) {
        resetRuntimePatchState();
      }
      return;
    }
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
      cssRules: Array.isArray(cssRules) ? cssRules : [],
      pageKey: getPageKey(),
      navigationEpoch: browserSession.navigationEpoch
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
    if (message.pageKey && message.pageKey !== getPageKey()) {
      return { ok: false, stale: true, expectedPageKey: getPageKey(), receivedPageKey: message.pageKey };
    }

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
        pageIdentity: message.pageIdentity || getPageIdentity(),
        pageSnapshot: message.pageSnapshot || null,
        editRecords: message.editRecords || [],
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
    const orderedKeys = keys.filter((key) => !cache[key]?.originalHtml).sort(
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
    const existing = cache[entry.pageKey] || {};
    cache[entry.pageKey] = {
      originalHtml: existing.originalHtml || entry.originalHtml || "",
      originalCapturedAt: existing.originalCapturedAt || entry.originalCapturedAt || "",
      patches: entry.patches,
      cssVars: entry.cssVars,
      cssRules: entry.cssRules || [],
      modifiedHtml: entry.modifiedHtml || "",
      sourcePrompt: entry.sourcePrompt,
      changesSummary: entry.changesSummary,
      traceId: entry.traceId,
      pageIdentity: entry.pageIdentity || getPageIdentity(entry.pageUrl),
      pageSnapshot: entry.pageSnapshot || null,
      editRecords: entry.editRecords || [],
      pageUrl: entry.pageUrl,
      updatedAt: new Date().toISOString()
    };
    const bounded = evictOldestEntries(cache, MAX_CACHED_PAGES);
    await chrome.storage.local.set({ [HTML_CACHE_KEY]: bounded });
  }

  async function clearPageCache() {
    const pageKey = getPageKey();
    const cache = await getHtmlCache();
    const existing = cache[pageKey];

    if (existing?.originalHtml) {
      cache[pageKey] = {
        originalHtml: existing.originalHtml,
        originalCapturedAt: existing.originalCapturedAt || "",
        pageUrl: existing.pageUrl || window.location.href,
        updatedAt: new Date().toISOString()
      };
    } else {
      delete cache[pageKey];
    }

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

  let selectionState = { active: false, reference: "", hovered: null, pending: false };
  let selectionHighlight = null;
  let selectionStyles = null;
  let selectionObserver = null;
  let selectionRefreshTimer = null;
  const selectionMarkers = new Map();
  let selectionMarkersVisible = false;

  function cssEscape(value) {
    if (window.CSS?.escape) {
      return window.CSS.escape(value);
    }
    return String(value).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
  }

  function cssString(value) {
    return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  function ensureSelectionStyles() {
    if (selectionStyles) {
      return;
    }
    selectionStyles = document.createElement("style");
    selectionStyles.id = "prism-element-selection-styles";
    selectionStyles.textContent = `
      #prism-element-highlight {
        position: fixed;
        z-index: 2147483646;
        pointer-events: none;
        border: 2px solid #F05454;
        background: rgba(240, 84, 84, 0.12);
        box-shadow: 0 0 0 4px rgba(240, 84, 84, 0.16);
        border-radius: 6px;
        transition: top 80ms ease, left 80ms ease, width 80ms ease, height 80ms ease;
      }
      .prism-selected-marker {
        position: fixed;
        z-index: 2147483645;
        pointer-events: none;
        border: 2px solid #F05454;
        background: rgba(48, 71, 94, 0.18);
        border-radius: 6px;
        box-shadow: 0 0 0 4px rgba(240, 84, 84, 0.14);
      }
      .prism-selected-marker::before {
        position: absolute;
        top: -26px;
        left: -2px;
        min-width: max-content;
        border-radius: 999px;
        padding: 4px 8px;
        background: #30475E;
        color: #DDDDDD;
        content: attr(data-prism-reference);
        font: 700 12px/1.2 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
    `;
    (document.head || document.documentElement).appendChild(selectionStyles);
  }

  function ensureSelectionHighlight() {
    ensureSelectionStyles();
    if (!selectionHighlight) {
      selectionHighlight = document.createElement("div");
      selectionHighlight.id = "prism-element-highlight";
      selectionHighlight.hidden = true;
      document.documentElement.appendChild(selectionHighlight);
    }
    return selectionHighlight;
  }

  function isExtensionSelectionUi(node) {
    return Boolean(
      node?.nodeType === Node.ELEMENT_NODE &&
        node.closest?.("#prism-element-highlight, .prism-selected-marker, #prism-element-selection-styles")
    );
  }

  function rectIsUsable(rect) {
    return rect && rect.width >= 4 && rect.height >= 4;
  }

  function isMeaningfulElement(el) {
    if (!el || el === document.documentElement || el === document.body) {
      return false;
    }
    const rect = el.getBoundingClientRect();
    if (!rectIsUsable(rect)) {
      return false;
    }
    const tag = el.tagName;
    const semanticTags = {
      A: 1,
      BUTTON: 1,
      IMG: 1,
      NAV: 1,
      ASIDE: 1,
      HEADER: 1,
      FOOTER: 1,
      MAIN: 1,
      SECTION: 1,
      ARTICLE: 1,
      FORM: 1,
      INPUT: 1,
      TEXTAREA: 1,
      SELECT: 1,
      LABEL: 1,
      CARD: 1
    };
    return Boolean(
      semanticTags[tag] ||
        el.id ||
        el.getAttribute("role") ||
        el.getAttribute("aria-label") ||
        el.getAttribute("data-testid") ||
        el.getAttribute("data-test") ||
        (typeof el.className === "string" && el.className.trim()) ||
        (el.textContent || "").trim()
    );
  }

  function nearestMeaningfulElement(raw) {
    let el = raw?.nodeType === Node.ELEMENT_NODE ? raw : raw?.parentElement;
    if (!el || isExtensionSelectionUi(el)) {
      return null;
    }

    const first = el;
    while (el && el !== document.documentElement && el !== document.body) {
      const rect = el.getBoundingClientRect();
      if (isMeaningfulElement(el) && (rect.width >= 16 || rect.height >= 16)) {
        return el;
      }
      el = el.parentElement;
    }
    return first;
  }

  function setOverlayRect(overlay, rect) {
    const next = {
      left: `${Math.max(0, Math.round(rect.left))}px`,
      top: `${Math.max(0, Math.round(rect.top))}px`,
      width: `${Math.round(rect.width)}px`,
      height: `${Math.round(rect.height)}px`
    };
    Object.entries(next).forEach(([property, value]) => {
      if (overlay.style[property] !== value) {
        overlay.style[property] = value;
      }
    });
  }

  function updateSelectionHighlight(el) {
    const overlay = ensureSelectionHighlight();
    if (!el) {
      overlay.hidden = true;
      return;
    }
    const rect = el.getBoundingClientRect();
    if (!rectIsUsable(rect)) {
      overlay.hidden = true;
      return;
    }
    setOverlayRect(overlay, rect);
    overlay.hidden = false;
  }

  function handleSelectionPointerMove(event) {
    if (!selectionState.active) {
      return;
    }
    const target = nearestMeaningfulElement(event.composedPath?.()[0] || event.target);
    selectionState.hovered = target;
    updateSelectionHighlight(target);
  }

  function blockSelectionEvent(event) {
    if (!selectionState.active) {
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  function uniqueSelectorCandidates(el) {
    const candidates = [];
    const tag = el.tagName.toLowerCase();
    if (el.id) {
      candidates.push(`#${cssEscape(el.id)}`);
      candidates.push(`${tag}#${cssEscape(el.id)}`);
    }
    ["data-testid", "data-test", "data-cy", "aria-label", "name", "role", "alt", "title"].forEach((name) => {
      const value = el.getAttribute(name);
      if (value) {
        candidates.push(`${tag}[${name}="${cssString(value)}"]`);
        candidates.push(`[${name}="${cssString(value)}"]`);
      }
    });
    if (typeof el.className === "string") {
      const classes = el.className.trim().split(/\s+/).filter(Boolean).slice(0, 4);
      if (classes.length) {
        candidates.push(`${tag}.${classes.map(cssEscape).join(".")}`);
      }
    }
    candidates.push(domPathSelector(el));
    return [...new Set(candidates)].filter((candidate) => {
      try {
        return document.querySelector(candidate);
      } catch (_error) {
        return false;
      }
    });
  }

  function nthOfType(el) {
    let index = 1;
    let node = el;
    while ((node = node.previousElementSibling)) {
      if (node.tagName === el.tagName) {
        index += 1;
      }
    }
    return `${el.tagName.toLowerCase()}:nth-of-type(${index})`;
  }

  function domPathSelector(el) {
    const steps = [];
    let node = el;
    while (node && node.nodeType === Node.ELEMENT_NODE && node !== document.documentElement) {
      if (node.id) {
        steps.unshift(`${node.tagName.toLowerCase()}#${cssEscape(node.id)}`);
        break;
      }
      steps.unshift(nthOfType(node));
      node = node.parentElement;
    }
    return steps.join(" > ");
  }

  function domPath(el) {
    const path = [];
    let node = el;
    while (node && node.nodeType === Node.ELEMENT_NODE && node !== document.documentElement) {
      path.unshift({
        tag: node.tagName.toLowerCase(),
        id: node.id || "",
        classes: typeof node.className === "string" ? node.className.trim().split(/\s+/).filter(Boolean) : [],
        nthOfType: nthOfType(node)
      });
      node = node.parentElement;
    }
    return path;
  }

  function compactText(value, limit = 160) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
  }

  function elementClasses(el, limit = 8) {
    return typeof el.className === "string"
      ? el.className.trim().split(/\s+/).filter(Boolean).slice(0, limit)
      : [];
  }

  function compactElementSummary(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) {
      return null;
    }
    const rect = el.getBoundingClientRect();
    return {
      tagName: el.tagName.toLowerCase(),
      id: el.id || "",
      classes: elementClasses(el, 5),
      role: el.getAttribute("role") || "",
      ariaLabel: el.getAttribute("aria-label") || "",
      text: compactText(el.innerText || el.textContent, 120),
      boundingBox: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      }
    };
  }

  function parentChain(el, limit = 5) {
    const parents = [];
    let node = el.parentElement;
    while (node && node !== document.body && node !== document.documentElement && parents.length < limit) {
      parents.push(compactElementSummary(node));
      node = node.parentElement;
    }
    return parents.filter(Boolean);
  }

  function siblingSummaries(el, direction, limit = 3) {
    const siblings = [];
    let node = direction === "previous" ? el.previousElementSibling : el.nextElementSibling;
    while (node && siblings.length < limit) {
      siblings.push(compactElementSummary(node));
      node = direction === "previous" ? node.previousElementSibling : node.nextElementSibling;
    }
    return siblings.filter(Boolean);
  }

  function childSummaries(el, limit = 6) {
    return Array.from(el.children || [])
      .slice(0, limit)
      .map(compactElementSummary)
      .filter(Boolean);
  }

  function selectedComputedStyles(el) {
    const style = window.getComputedStyle(el);
    const properties = [
      "display",
      "position",
      "inset",
      "top",
      "right",
      "bottom",
      "left",
      "zIndex",
      "width",
      "height",
      "minWidth",
      "minHeight",
      "maxWidth",
      "maxHeight",
      "margin",
      "padding",
      "color",
      "backgroundColor",
      "backgroundImage",
      "border",
      "borderRadius",
      "boxShadow",
      "opacity",
      "fontFamily",
      "fontSize",
      "fontWeight",
      "lineHeight",
      "textAlign",
      "transform",
      "overflow",
      "overflowX",
      "overflowY",
      "flex",
      "flexDirection",
      "alignItems",
      "justifyContent",
      "gridTemplateColumns",
      "gridTemplateRows"
    ];
    return properties.reduce((acc, property) => {
      acc[property] = style[property] || "";
      return acc;
    }, {});
  }

  function selectedElementContext(el) {
    return {
      parentChain: parentChain(el),
      previousSiblings: siblingSummaries(el, "previous"),
      nextSiblings: siblingSummaries(el, "next"),
      children: childSummaries(el),
      childElementCount: el.children?.length || 0
    };
  }

  function selectedElementRecord(el, reference) {
    const rect = el.getBoundingClientRect();
    const dataAttributes = {};
    const attributes = {};
    Array.from(el.attributes || []).forEach((attr) => {
      if (attr.name.startsWith("data-")) {
        dataAttributes[attr.name] = attr.value.slice(0, 160);
      }
      if ([
        "href",
        "src",
        "alt",
        "title",
        "name",
        "type",
        "role",
        "aria-label",
        "aria-labelledby",
        "aria-describedby",
        "placeholder",
        "value"
      ].includes(attr.name)) {
        attributes[attr.name] = attr.value.slice(0, 200);
      }
    });
    const text = compactText(el.innerText || el.textContent, 240);
    const classes = elementClasses(el);
    const box = {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      top: Math.round(rect.top + window.scrollY),
      left: Math.round(rect.left + window.scrollX)
    };
    return {
      reference,
      pageUrl: window.location.href,
      pageKey: getPageKey(),
      selectorCandidates: uniqueSelectorCandidates(el),
      domPath: domPath(el),
      visibleText: text,
      tagName: el.tagName.toLowerCase(),
      id: el.id || "",
      classes,
      dataAttributes,
      attributes,
      boundingBox: box,
      computedStyles: selectedComputedStyles(el),
      domContext: selectedElementContext(el),
      visualPosition: {
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        scrollX: window.scrollX,
        scrollY: window.scrollY
      },
      screenshotContext: {
        available: false,
        reason: "No screenshot capture is requested for element selection yet."
      },
      semanticRole: el.getAttribute("role") || el.getAttribute("aria-label") || "",
      fingerprint: stableHash(`${el.tagName}|${el.id}|${classes.join(".")}|${text}|${box.width}x${box.height}`),
      selectedAt: new Date().toISOString()
    };
  }

  function selectedElementFingerprint(el) {
    const rect = el.getBoundingClientRect();
    const classes = typeof el.className === "string" ? el.className.trim().split(/\s+/).filter(Boolean) : [];
    const text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 240);
    return stableHash(`${el.tagName}|${el.id}|${classes.join(".")}|${text}|${Math.round(rect.width)}x${Math.round(rect.height)}`);
  }

  function replacementScore(el, record) {
    let score = 0;
    if (record.fingerprint && selectedElementFingerprint(el) === record.fingerprint) score += 100;
    if (record.id && el.id === record.id) score += 40;
    if (record.tagName && el.tagName.toLowerCase() === record.tagName) score += 20;
    const text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 240);
    if (record.visibleText && text === record.visibleText) score += 30;
    return score;
  }

  function findReplacementElement(record) {
    if (!record || !Array.isArray(record.selectorCandidates)) {
      return null;
    }

    const matches = [];
    record.selectorCandidates.forEach((selector) => {
      try {
        document.querySelectorAll(selector).forEach((candidate) => {
          if (!isExtensionSelectionUi(candidate) && rectIsUsable(candidate.getBoundingClientRect())) {
            matches.push(candidate);
          }
        });
      } catch (_error) {
        // Ignore stale or invalid selector candidates.
      }
    });

    return [...new Set(matches)]
      .map((candidate) => ({ candidate, score: replacementScore(candidate, record) }))
      .sort((a, b) => b.score - a.score)[0]?.candidate || null;
  }

  function placeSelectedMarker(reference, el, record = null) {
    ensureSelectionStyles();
    let marker = selectionMarkers.get(reference)?.marker;
    if (!marker) {
      marker = document.createElement("div");
      marker.className = "prism-selected-marker";
      marker.dataset.prismReference = reference;
      document.documentElement.appendChild(marker);
    }
    setOverlayRect(marker, el.getBoundingClientRect());
    marker.hidden = !selectionMarkersVisible;
    selectionMarkers.set(reference, { el, marker, record });
    ensureSelectionObserver();
  }

  function restoreSelectedMarkers(records = [], visible = true) {
    selectionMarkersVisible = Boolean(visible);
    clearSelectedElementMarkers();
    records.forEach((record) => {
      const target = findReplacementElement(record);
      if (!target) {
        return;
      }
      placeSelectedMarker(record.reference, target, record);
      const selected = selectionMarkers.get(record.reference);
      if (selected?.marker) {
        selected.marker.hidden = !visible;
      }
    });
  }

  function refreshSelectedMarkers() {
    selectionMarkers.forEach(({ el, marker, record }, reference) => {
      if (!document.documentElement.contains(el)) {
        const replacement = findReplacementElement(record);
        if (!replacement) {
          marker.hidden = true;
          return;
        }
        el = replacement;
        marker.hidden = false;
        selectionMarkers.set(reference, { el, marker, record });
      }
      const rect = el.getBoundingClientRect();
      marker.hidden = !selectionMarkersVisible || !rectIsUsable(rect);
      if (!marker.hidden) {
        setOverlayRect(marker, rect);
      }
    });
  }

  function refreshSelectionUi() {
    if (selectionState.active) {
      updateSelectionHighlight(selectionState.hovered);
    }
    refreshSelectedMarkers();
  }

  function scheduleSelectionRefresh() {
    window.clearTimeout(selectionRefreshTimer);
    selectionRefreshTimer = window.setTimeout(refreshSelectionUi, 50);
  }

  function ensureSelectionObserver() {
    if (selectionObserver || !document.documentElement) {
      return;
    }
    selectionObserver = new MutationObserver((mutations) => {
      const pageChanged = mutations.some((mutation) => !isExtensionSelectionUi(mutation.target));
      if (pageChanged) {
        scheduleSelectionRefresh();
      }
    });
    selectionObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true
    });
  }

  function stopSelectionObserverIfIdle() {
    if (selectionState.active || selectionMarkers.size || !selectionObserver) {
      return;
    }
    selectionObserver.disconnect();
    selectionObserver = null;
    window.clearTimeout(selectionRefreshTimer);
    selectionRefreshTimer = null;
  }

  function forgetSelectedElement(reference) {
    const selected = selectionMarkers.get(reference);
    if (selected?.marker) {
      selected.marker.remove();
    }
    selectionMarkers.delete(reference);
    stopSelectionObserverIfIdle();
  }

  function clearSelectedElementMarkers() {
    selectionMarkers.forEach(({ marker }) => marker.remove());
    selectionMarkers.clear();
    stopSelectionObserverIfIdle();
  }

  function selectedReferenceForElement(target) {
    if (!target) {
      return "";
    }
    const fingerprint = selectedElementFingerprint(target);
    for (const [reference, selected] of selectionMarkers.entries()) {
      if (selected.el === target || selected.record?.fingerprint === fingerprint) {
        return reference;
      }
    }
    return "";
  }

  function handleSelectionClick(event) {
    if (!selectionState.active) {
      return;
    }
    blockSelectionEvent(event);
    if (selectionState.pending) {
      return;
    }
    const target = selectionState.hovered || nearestMeaningfulElement(event.composedPath?.()[0] || event.target);
    if (!target) {
      return;
    }

    const selectedReference = selectedReferenceForElement(target);
    if (selectedReference) {
      selectionState.pending = true;
      chrome.runtime.sendMessage({
        type: "ELEMENT_DESELECTED",
        payload: { reference: selectedReference }
      }, (response) => {
        selectionState.pending = false;
        if (!selectionState.active) {
          return;
        }
        if (chrome.runtime.lastError || response?.status === "error" || !response?.ok) {
          stopElementSelection();
          return;
        }
        selectionState.reference = response.nextReference || selectionState.reference;
        restoreSelectedMarkers(response.selectedElements || [], true);
        updateSelectionHighlight(selectionState.hovered);
      });
      return;
    }

    const reference = selectionState.reference;
    const record = selectedElementRecord(target, reference);
    placeSelectedMarker(reference, target, record);
    selectionState.pending = true;
    chrome.runtime.sendMessage({
      type: "ELEMENT_SELECTED",
      payload: { element: record }
    }, (response) => {
      selectionState.pending = false;
      if (!selectionState.active) {
        return;
      }
      if (chrome.runtime.lastError || response?.status === "error" || !response?.ok) {
        stopElementSelection();
        return;
      }
      selectionState.reference = response.nextReference || selectionState.reference;
      if (Array.isArray(response.selectedElements)) {
        restoreSelectedMarkers(response.selectedElements, true);
      }
      updateSelectionHighlight(selectionState.hovered);
    });
  }

  function handleSelectionKeydown(event) {
    if (selectionState.active && event.key === "Escape") {
      blockSelectionEvent(event);
      stopElementSelection({ hideMarkers: true });
      chrome.runtime.sendMessage({ type: "ELEMENT_SELECTION_CANCELLED" });
    }
  }

  function startElementSelection(reference, selectedElements = []) {
    stopElementSelection();
    selectionState = { active: true, reference: reference || "element1", hovered: null, pending: false };
    ensureSelectionHighlight();
    restoreSelectedMarkers(selectedElements, true);
    ensureSelectionObserver();
    document.addEventListener("pointermove", handleSelectionPointerMove, true);
    document.addEventListener("pointerdown", blockSelectionEvent, true);
    document.addEventListener("mousedown", blockSelectionEvent, true);
    document.addEventListener("mouseup", blockSelectionEvent, true);
    document.addEventListener("click", handleSelectionClick, true);
    document.addEventListener("dblclick", blockSelectionEvent, true);
    document.addEventListener("auxclick", blockSelectionEvent, true);
    document.addEventListener("keydown", handleSelectionKeydown, true);
    window.addEventListener("scroll", refreshSelectedMarkers, true);
    window.addEventListener("resize", refreshSelectedMarkers, true);
  }

  function updateElementSelection(reference, selectedElements = [], markersVisible = selectionState.active) {
    if (selectionState.active && reference) {
      selectionState.reference = reference;
    }
    restoreSelectedMarkers(selectedElements, Boolean(markersVisible));
  }

  function stopElementSelection(options = {}) {
    document.removeEventListener("pointermove", handleSelectionPointerMove, true);
    document.removeEventListener("pointerdown", blockSelectionEvent, true);
    document.removeEventListener("mousedown", blockSelectionEvent, true);
    document.removeEventListener("mouseup", blockSelectionEvent, true);
    document.removeEventListener("click", handleSelectionClick, true);
    document.removeEventListener("dblclick", blockSelectionEvent, true);
    document.removeEventListener("auxclick", blockSelectionEvent, true);
    document.removeEventListener("keydown", handleSelectionKeydown, true);
    selectionState = { active: false, reference: "", hovered: null, pending: false };
    if (selectionHighlight) {
      selectionHighlight.hidden = true;
    }
    if (options.hideMarkers) {
      clearSelectedElementMarkers();
    }
    stopSelectionObserverIfIdle();
  }

  function resetRuntimePatchState() {
    patchState = { patches: [], cssVars: {}, cssRules: [], pageKey: getPageKey(), navigationEpoch: browserSession.navigationEpoch };
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    clearTimeout(debounceTimer);
    const style = document.getElementById("prism-overrides");
    if (style) style.remove();
  }

  function handleNavigationMaybe() {
    const identity = getPageIdentity();
    if (identity.canonicalUrl === browserSession.pageKey) {
      return;
    }
    browserSession = {
      currentUrl: window.location.href,
      pageKey: identity.canonicalUrl,
      routeKey: identity.routeKey,
      navigationEpoch: browserSession.navigationEpoch + 1,
      liveDomValid: false
    };
    const hadActiveSelection = selectionState.active;
    resetRuntimePatchState();
    stopElementSelection();
    clearSelectedElementMarkers();
    if (hadActiveSelection) {
      chrome.runtime.sendMessage({ type: "ELEMENT_SELECTION_CANCELLED" });
    }
    window.setTimeout(() => {
      browserSession.liveDomValid = true;
      applyCachedPatches();
    }, 120);
  }

  function installNavigationInvalidation() {
    const wrapHistory = (name) => {
      const original = history[name];
      history[name] = function wrappedHistoryState() {
        const result = original.apply(this, arguments);
        window.setTimeout(handleNavigationMaybe, 0);
        return result;
      };
    };
    wrapHistory("pushState");
    wrapHistory("replaceState");
    window.addEventListener("popstate", handleNavigationMaybe);
    window.addEventListener("hashchange", handleNavigationMaybe);
    window.addEventListener("pageshow", handleNavigationMaybe);
    window.setInterval(handleNavigationMaybe, NAVIGATION_POLL_MS);
  }

  installNavigationInvalidation();
})();
