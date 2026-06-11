const promptInput = document.querySelector("#promptInput");
const applyPrompt = document.querySelector("#applyPrompt");
const composerStatus = document.querySelector("#composerStatus");
const tabTitle = document.querySelector("#tabTitle");
const tabUrl = document.querySelector("#tabUrl");
const modeRow = document.querySelector("#modeRow");
const currentCache = document.querySelector("#currentCache");
const historyToggle = document.querySelector("#historyToggle");
const historyArrow = document.querySelector("#historyArrow");
const historyPanel = document.querySelector("#historyPanel");
const historyList = document.querySelector("#historyList");
const detailPane = document.querySelector("#detailPane");
const detailText = document.querySelector("#detailText");
const detailMode = document.querySelector("#detailMode");
const openSettings = document.querySelector("#openSettings");
const clearAllPopupCache = document.querySelector("#clearAllPopupCache");
const startElementPick = document.querySelector("#startElementPick");
const cancelElementPick = document.querySelector("#cancelElementPick");
const selectedElementsList = document.querySelector("#selectedElementsList");

const TOKEN_LIMIT = 1000000;
const CHARS_PER_TOKEN = 4;
const HTML_CACHE_KEY = "domHtmlCache";
const POPUP_TAB_STATE_KEY = "popupTabPromptState";
const TRACKING_QUERY_NAMES = new Set(["fbclid", "gclid", "msclkid"]);
// Modes are owned by the backend. We fetch [{key,label}] and render buttons;
// the chosen key is sent and the backend resolves its instruction. No
// instruction text lives here. `modeButtons` is populated by renderModes().
let modeList = [];
let modeButtons = [];

function knownModeKeys() {
  return new Set(modeList.map((m) => m.key));
}

function renderModes(modes) {
  modeList = Array.isArray(modes) ? modes : [];
  modeRow.innerHTML = "";
  modeButtons = modeList.map((m) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mode-button";
    button.dataset.mode = m.key;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", "false");
    button.textContent = m.label;
    button.addEventListener("click", () => {
      setSelectedMode(selectedMode === m.key ? null : m.key);
    });
    modeRow.appendChild(button);
    return button;
  });
  // Re-assert any restored selection now that buttons exist.
  setSelectedMode(normalizeMode(selectedMode), false);
}

async function loadModes() {
  try {
    const res = await sendRuntimeMessage({ type: "FETCH_MODES" }, 5000);
    if (res?.ok && Array.isArray(res.modes)) {
      renderModes(res.modes);
      if (!res.modes.length) {
        setComposerStatus("No modes configured on the backend.", "error");
      }
      return;
    }
    // Surface why instead of silently showing an empty mode row.
    renderModes([]);
    const reason = res?.error?.message || "Unknown error";
    setComposerStatus(
      `Couldn't load modes: ${reason}. Is the backend up to date and running?`,
      "error"
    );
  } catch (error) {
    renderModes([]); // still usable for free-form prompts
    setComposerStatus(
      `Couldn't load modes: ${error.message || "API unreachable"}.`,
      "error"
    );
  }
}

let activeTab = null;
let activeTabKey = null;
let selectedMode = null;
let currentTabState = createEmptyTabState();
let saveTimer = null;
let statusTimer = null;
let lastPromptEditAt = 0;

function createEmptyTabState() {
  return {
    draftPrompt: "",
    draftMode: null,
    current: null,
    history: [],
    nextIndex: 1,
    historyExpanded: false,
    selectedElements: [],
    nextElementIndex: 1,
    promptSelectionStart: 0,
    promptSelectionEnd: 0,
    selectionMode: false
  };
}

function normalizeTabState(state = {}) {
  return renumberVersionIndexes(dedupeOriginalVersions({
    ...createEmptyTabState(),
    ...state,
    draftMode: normalizeMode(state.draftMode),
    current: normalizeVersion(state.current),
    history: Array.isArray(state.history) ? state.history.map(normalizeVersion).filter(Boolean) : [],
    nextIndex: Number.isInteger(state.nextIndex) && state.nextIndex > 0 ? state.nextIndex : 1,
    historyExpanded: Boolean(state.historyExpanded),
    selectedElements: Array.isArray(state.selectedElements)
      ? state.selectedElements.map(normalizeSelectedElement).filter(Boolean)
      : [],
    nextElementIndex: Number.isInteger(state.nextElementIndex) && state.nextElementIndex > 0
      ? state.nextElementIndex
      : 1,
    promptSelectionStart: Number.isInteger(state.promptSelectionStart) ? state.promptSelectionStart : 0,
    promptSelectionEnd: Number.isInteger(state.promptSelectionEnd) ? state.promptSelectionEnd : 0,
    selectionMode: Boolean(state.selectionMode)
  }));
}

function normalizeSelectedElement(element) {
  if (!element || typeof element !== "object" || !element.reference) {
    return null;
  }

  return {
    reference: String(element.reference),
    pageUrl: element.pageUrl || "",
    pageKey: element.pageKey || "",
    selectorCandidates: Array.isArray(element.selectorCandidates) ? element.selectorCandidates : [],
    domPath: Array.isArray(element.domPath) ? element.domPath : [],
    visibleText: element.visibleText || "",
    tagName: element.tagName || "",
    id: element.id || "",
    classes: Array.isArray(element.classes) ? element.classes : [],
    dataAttributes: element.dataAttributes && typeof element.dataAttributes === "object"
      ? element.dataAttributes
      : {},
    attributes: element.attributes && typeof element.attributes === "object" ? element.attributes : {},
    boundingBox: element.boundingBox || {},
    computedStyles: element.computedStyles && typeof element.computedStyles === "object"
      ? element.computedStyles
      : {},
    domContext: element.domContext && typeof element.domContext === "object" ? element.domContext : {},
    visualPosition: element.visualPosition || {},
    screenshotContext: element.screenshotContext && typeof element.screenshotContext === "object"
      ? element.screenshotContext
      : {},
    semanticRole: element.semanticRole || "",
    fingerprint: element.fingerprint || "",
    selectedAt: element.selectedAt || new Date().toISOString()
  };
}

function normalizeVersion(version) {
  if (!version || typeof version !== "object") {
    return null;
  }

  return {
    id: version.id || createId(),
    index: Number.isInteger(version.index) ? version.index : 0,
    prompt: typeof version.prompt === "string" ? version.prompt : "",
    mode: normalizeMode(version.mode),
    createdAt: version.createdAt || new Date().toISOString(),
    kind: version.kind || "generated",
    result: version.result || null,
    deltaResult: version.deltaResult || null,
    baseResult: version.baseResult || null,
    parentVersionId: version.parentVersionId || null,
    mergeMode: version.mergeMode || "replace",
    pending: Boolean(version.pending)
  };
}

function normalizeMode(mode) {
  if (mode == null) return null;
  // Tolerate old numeric/persisted values; any key not in the backend's
  // mode list (retired/unknown) resolves to no mode.
  const legacyNumeric = { 1: "focus", 2: "modernization", 3: "mode3", 4: "mode4" };
  const key = Object.hasOwn(legacyNumeric, mode) ? legacyNumeric[mode] : mode;
  if (!modeList.length) {
    return key;
  }
  return knownModeKeys().has(key) ? key : null;
}

function createId() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function nextElementReference(elements = []) {
  const used = new Set(
    elements
      .map((element) => element?.reference)
      .filter((reference) => typeof reference === "string")
  );
  let index = elements.length + 1;
  while (used.has(`element${index}`)) {
    index += 1;
  }
  return `element${index}`;
}

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

function getPageIdentity(url) {
  const parsedUrl = new URL(url);
  const query = semanticQuery(parsedUrl.search);
  const hashRoute = routeHash(parsedUrl.hash);
  let routeKey = parsedUrl.pathname || "/";
  if (query) routeKey += `?${query}`;
  if (hashRoute) routeKey += `#${hashRoute}`;
  const canonicalUrl = `${parsedUrl.origin}${routeKey}`;
  return {
    pageId: stableHash(`${parsedUrl.origin}|${routeKey}`),
    websiteId: stableHash(parsedUrl.origin),
    origin: parsedUrl.origin,
    path: parsedUrl.pathname || "/",
    routeKey,
    canonicalUrl,
    queryPolicy: "semantic",
    hashPolicy: "route-only",
    viewportVariant: "default",
    authVariant: "unknown"
  };
}

function getPageKey(url) {
  return getPageIdentity(url).canonicalUrl;
}

function getSiteKey(url) {
  const parsedUrl = new URL(url);
  if (parsedUrl.protocol === "file:") {
    return "file:";
  }

  return parsedUrl.origin;
}

// Templates are per-page (origin + path) so /projects/ keeps its own
// versions, separate from / on the same site — matching how the HTML
// cache is keyed. Non-URL tabs (chrome://, new tab) fall back to tab id.
function pageStateKey(tab) {
  try {
    return getPageKey(tab.url || "");
  } catch (_error) {
    return `tab:${tab?.id}`;
  }
}

function isOriginalVersion(version) {
  return version?.kind === "original";
}

function hasOriginalVersion(state) {
  return Boolean(
    isOriginalVersion(state.current) || (state.history || []).some((version) => isOriginalVersion(version))
  );
}

function hasGeneratedVersion(state) {
  return Boolean(
    (state.current && !isOriginalVersion(state.current)) ||
      (state.history || []).some((version) => !isOriginalVersion(version))
  );
}

function dedupeOriginalVersions(state) {
  let originalSeen = false;
  const keepVersion = (version) => {
    if (!isOriginalVersion(version)) {
      return true;
    }

    if (originalSeen) {
      return false;
    }

    originalSeen = true;
    return true;
  };

  const current = state.current && keepVersion(state.current) ? state.current : null;
  const history = (state.history || []).filter(keepVersion);
  return { ...state, current, history };
}

function estimateTokens(text) {
  return Math.ceil((text ? text.length : 0) / CHARS_PER_TOKEN);
}

function resolveTokens(snapshot) {
  if (typeof snapshot?.estimatedTokens === "number") {
    return snapshot.estimatedTokens;
  }

  return estimateTokens(snapshot?.html || "");
}

function getLastRuntimeError() {
  return chrome.runtime.lastError?.message;
}

function setComposerStatus(message = "", state = "ready", autoClear = false) {
  window.clearTimeout(statusTimer);
  composerStatus.textContent = message;
  composerStatus.classList.toggle("visible", Boolean(message));
  composerStatus.classList.toggle("error", state === "error");

  if (message && autoClear) {
    statusTimer = window.setTimeout(() => {
      setComposerStatus();
    }, 2600);
  }
}

function setGenerateBusy(isBusy) {
  applyPrompt.disabled = isBusy;
  applyPrompt.textContent = isBusy ? "Generating..." : "Generate";
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab?.id) {
    throw new Error("No active tab found.");
  }

  return tab;
}

function canRunOnTab(tab) {
  return /^https?:|^file:/.test(tab.url || "");
}

function explainBlockedTab(tab) {
  if ((tab.url || "").startsWith("file:")) {
    return "This is a local file. Enable 'Allow access to file URLs' for the extension in chrome://extensions.";
  }

  return "Open a normal http/https page. Chrome blocks extensions on this page.";
}

function sendTabMessage(tabId, message, timeoutMs = 6000) {
  return new Promise((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      reject(new Error("Page script did not respond. Reload the page and try again."));
    }, timeoutMs);

    chrome.tabs.sendMessage(tabId, message, (response) => {
      window.clearTimeout(timeoutId);
      const error = getLastRuntimeError();

      if (error) {
        reject(new Error(error));
        return;
      }

      resolve(response);
    });
  });
}

function injectContentScript(tabId) {
  return new Promise((resolve, reject) => {
    if (!chrome.scripting?.executeScript) {
      reject(new Error("Chrome has not loaded the scripting permission yet. Reload the extension, then reopen this page."));
      return;
    }

    chrome.scripting.executeScript(
      {
        target: { tabId },
        files: ["src/content.js"]
      },
      () => {
        const error = getLastRuntimeError();

        if (error) {
          reject(new Error(error));
          return;
        }

        resolve();
      }
    );
  });
}

async function ensureContentScript(tab) {
  if (!canRunOnTab(tab)) {
    throw new Error(explainBlockedTab(tab));
  }

  try {
    await sendTabMessage(tab.id, { type: "PING_CONTENT_SCRIPT" }, 1500);
  } catch (error) {
    if (!error.message.includes("Receiving end does not exist")) {
      throw error;
    }

    await injectContentScript(tab.id);
    await sendTabMessage(tab.id, { type: "PING_CONTENT_SCRIPT" }, 1500);
  }
}

function sendRuntimeMessage(message, timeoutMs = 7000) {
  return new Promise((resolve, reject) => {
    const timeoutId =
      timeoutMs > 0
        ? window.setTimeout(() => {
            reject(new Error("Extension background worker did not respond. Reload the extension."));
          }, timeoutMs)
        : null;

    chrome.runtime.sendMessage(message, (response) => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }

      const error = getLastRuntimeError();

      if (error) {
        reject(new Error(error));
        return;
      }

      resolve(response);
    });
  });
}

async function getPopupStore() {
  const data = await chrome.storage.local.get(POPUP_TAB_STATE_KEY);
  return data[POPUP_TAB_STATE_KEY] || {};
}

async function persistTabState() {
  if (!activeTabKey) {
    return;
  }

  const store = await getPopupStore();
  store[activeTabKey] = currentTabState;
  await chrome.storage.local.set({ [POPUP_TAB_STATE_KEY]: store });
}

function setPromptValue(value, options = {}) {
  const nextValue = typeof value === "string" ? value : "";
  if (promptInput.value === nextValue) {
    return;
  }

  const shouldFocus = options.focus || document.activeElement === promptInput;
  const start = Number.isInteger(options.selectionStart)
    ? options.selectionStart
    : promptInput.selectionStart;
  const end = Number.isInteger(options.selectionEnd)
    ? options.selectionEnd
    : promptInput.selectionEnd;
  promptInput.value = nextValue;

  if (shouldFocus) {
    promptInput.focus();
    const boundedStart = Math.min(Math.max(start || 0, 0), nextValue.length);
    const boundedEnd = Math.min(Math.max(end || boundedStart, 0), nextValue.length);
    promptInput.setSelectionRange(boundedStart, boundedEnd);
  }
}

function rememberPromptSelection() {
  currentTabState.promptSelectionStart = promptInput.selectionStart || 0;
  currentTabState.promptSelectionEnd = promptInput.selectionEnd || currentTabState.promptSelectionStart;
}

function syncPromptDraftFromInput() {
  rememberPromptSelection();
  currentTabState.draftPrompt = promptInput.value;
  currentTabState.draftMode = selectedMode;
  lastPromptEditAt = Date.now();
}

function hasLocalPromptActivity() {
  return (
    document.activeElement === promptInput ||
    saveTimer !== null ||
    Date.now() - lastPromptEditAt < 900
  );
}

async function refreshTabStateFromStorage() {
  if (!activeTabKey) {
    return;
  }

  const store = await getPopupStore();
  currentTabState = normalizeTabState(store[activeTabKey]);
  setPromptValue(currentTabState.draftPrompt, {
    selectionStart: currentTabState.promptSelectionStart,
    selectionEnd: currentTabState.promptSelectionEnd
  });
  setSelectedMode(currentTabState.draftMode, false);
  renderSelectedElements();
  renderCacheState();
}

function scheduleDraftSave() {
  if (!activeTabKey) {
    return;
  }

  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    persistTabState().catch(() => {});
  }, 150);
}

function setSelectedMode(mode, shouldPersist = true) {
  selectedMode = normalizeMode(mode);

  modeButtons.forEach((button) => {
    const isSelected = button.dataset.mode === selectedMode;
    button.classList.toggle("selected", isSelected);
    button.setAttribute("aria-checked", String(isSelected));
  });

  if (shouldPersist) {
    currentTabState.draftMode = selectedMode;
    scheduleDraftSave();
  }
}

function modeLabel(mode) {
  return modeList.find((m) => m.key === mode)?.label || "";
}

function compactPrompt(prompt) {
  return (prompt || "").replace(/\s+/g, " ").trim();
}

function previewVersion(version) {
  if (version.kind === "original") {
    return "Original page version";
  }

  if (version.pending) {
    return "Generating...";
  }

  const prompt = compactPrompt(version.prompt);

  if (prompt) {
    return `${prompt.slice(0, 30)}...`;
  }

  if (version.mode) {
    return `${modeLabel(version.mode)} was selected`;
  }

  return "Empty prompt";
}

function createTextElement(className, text) {
  const element = document.createElement("span");
  element.className = className;
  element.textContent = text;
  return element;
}

function detailContentFor(version) {
  let text = "";
  if (version.kind === "original") {
    text = "Original page version captured before the first generated change.";
  } else if (version.prompt.trim()) {
    text = version.prompt.trim();
  } else if (version.pending) {
    text = "This generated version is still waiting for the API result.";
  }
  if (version.result?.mergeSummary) {
    const summary = version.result.mergeSummary;
    const mergeLine = `Merged update: ${summary.basePatchCount || 0} previous patches + ${summary.deltaPatchCount || 0} new patches.`;
    text = [text, mergeLine].filter(Boolean).join("\n\n");
  }
  if (version.result?.mergeConflicts?.length) {
    text = [text, `${version.result.mergeConflicts.length} merge conflict marker(s) were recorded.`]
      .filter(Boolean)
      .join("\n\n");
  }
  return { text, mode: version.mode ? modeLabel(version.mode) : "" };
}

// Which card's detail is currently expanded in the side pane (null = closed).
let expandedVersionId = null;

function collapseDetailPane() {
  expandedVersionId = null;
  detailPane.classList.remove("open");
  detailPane.setAttribute("aria-hidden", "true");
  document
    .querySelectorAll(".version-card.detail-active")
    .forEach((el) => el.classList.remove("detail-active"));
}

function openDetailPane(version) {
  const { text, mode } = detailContentFor(version);
  if (!text && !mode) {
    collapseDetailPane();
    return;
  }
  expandedVersionId = version.id;
  detailText.textContent = text;
  detailMode.textContent = mode;
  detailMode.hidden = !mode;
  detailPane.classList.add("open");
  detailPane.setAttribute("aria-hidden", "false");
  document
    .querySelectorAll(".version-card.detail-active")
    .forEach((el) => el.classList.remove("detail-active"));
  const card = document.querySelector(`.version-card[data-version-id="${version.id}"]`);
  if (card) card.classList.add("detail-active");
}

// Click a card to slide the pane open; click the same card again to close.
function toggleDetailPane(version) {
  if (expandedVersionId === version.id) {
    collapseDetailPane();
  } else {
    openDetailPane(version);
  }
}

// After a re-render the cards are rebuilt; drop the pane if its version
// is gone, otherwise re-mark the active card.
function reconcileDetailPane() {
  if (expandedVersionId === null) {
    return;
  }
  const stillExists =
    currentTabState.current?.id === expandedVersionId ||
    (currentTabState.history || []).some((v) => v.id === expandedVersionId);
  if (!stillExists) {
    collapseDetailPane();
    return;
  }
  const card = document.querySelector(
    `.version-card[data-version-id="${expandedVersionId}"]`
  );
  if (card) card.classList.add("detail-active");
}

function versionMetaText(version, placement) {
  if (version.pending) {
    return "Generating";
  }
  if (isOriginalVersion(version)) {
    return "Base";
  }
  const count = (version.result?.patches || []).length;
  const mergeLabel = version.result?.mergeMode === "merge" || version.mergeMode === "merge"
    ? "Merged"
    : "Template";
  const currentLabel = placement === "current" ? "Editing" : "Saved";
  return [currentLabel, mergeLabel, count ? `${count} ops` : ""].filter(Boolean).join(" · ");
}

function appendVersionAction(actions, label, action, versionId, className = "") {
  const button = document.createElement("button");
  button.className = `version-menu-item ${className}`.trim();
  button.type = "button";
  button.dataset.action = action;
  button.dataset.versionId = versionId;
  button.textContent = label;
  actions.append(button);
}

function createVersionActions(version, placement) {
  const actions = document.createElement("div");
  actions.className = "version-actions";

  const trigger = document.createElement("button");
  trigger.className = "version-menu-trigger";
  trigger.type = "button";
  trigger.setAttribute("aria-label", "Template actions");
  trigger.textContent = "...";

  const menu = document.createElement("div");
  menu.className = "version-action-menu";

  if (placement === "history") {
    const canRestore = isOriginalVersion(version) || Boolean(version.prompt || version.mode);
    appendVersionAction(menu, "Restore", "rollback", version.id);
    menu.lastElementChild.disabled = version.pending || !canRestore;
  }

  if (!isOriginalVersion(version)) {
    appendVersionAction(
      menu,
      "Delete",
      placement === "history" ? "delete-history" : "delete-current",
      version.id,
      "danger"
    );
  }

  if (!menu.children.length) {
    return null;
  }

  actions.append(trigger, menu);
  return actions;
}

function createVersionCard(version, placement) {
  const card = document.createElement("article");
  card.className = `version-card ${placement === "current" ? "current-card" : "history-card"}`;
  card.dataset.versionId = version.id;
  card.tabIndex = 0;
  card.classList.toggle("protected-card", isOriginalVersion(version));

  card.append(createTextElement("version-index", `#${version.index}`));
  const body = document.createElement("div");
  body.className = "version-body";
  body.append(createTextElement("version-preview", previewVersion(version)));
  body.append(createTextElement("version-meta", versionMetaText(version, placement)));
  card.append(body);

  if (placement === "current") {
    card.append(createTextElement("current-chip", "Editing"));
  }

  const actions = createVersionActions(version, placement);
  if (actions) {
    card.append(actions);
  }

  card.addEventListener("click", (event) => {
    // Rollback / Delete buttons keep their own behaviour.
    if (event.target.closest("button")) return;
    toggleDetailPane(version);
  });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      if (event.target.closest("button")) return;
      event.preventDefault();
      toggleDetailPane(version);
    }
  });
  return card;
}

function sortHistory(history) {
  return [...history].sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
}

function renumberVersionIndexes(state) {
  const versions = [state.current, ...(state.history || [])].filter(Boolean);
  const ordered = [...versions].sort((a, b) => {
    const byDate = Date.parse(a.createdAt || "") - Date.parse(b.createdAt || "");
    if (Number.isFinite(byDate) && byDate !== 0) {
      return byDate;
    }

    return String(a.id || "").localeCompare(String(b.id || ""));
  });
  const indexById = new Map(ordered.map((version, index) => [version.id, index + 1]));
  const applyIndex = (version) =>
    version
      ? {
          ...version,
          index: indexById.get(version.id) || 1
        }
      : null;

  return {
    ...state,
    current: applyIndex(state.current),
    history: (state.history || []).map(applyIndex),
    nextIndex: versions.length + 1
  };
}

function renderCurrentCache() {
  currentCache.replaceChildren();

  if (!currentTabState.current && !currentTabState.history.length) {
    const empty = document.createElement("p");
    empty.className = "empty-cache";
    empty.textContent = "no saves";
    currentCache.append(empty);
    return;
  }

  if (currentTabState.current) {
    currentCache.append(createVersionCard(currentTabState.current, "current"));
  }
}

function renderHistory() {
  const expanded = Boolean(currentTabState.historyExpanded);
  historyToggle.setAttribute("aria-expanded", String(expanded));
  historyArrow.textContent = "";
  historyArrow.classList.toggle("expanded", expanded);
  historyPanel.hidden = !expanded;
  historyList.replaceChildren();

  if (!expanded) {
    return;
  }

  const history = sortHistory(currentTabState.history);
  if (!history.length && currentTabState.current) {
    const empty = document.createElement("p");
    empty.className = "empty-history";
    empty.textContent = "no older saves";
    historyList.append(empty);
    return;
  }

  history.forEach((version) => {
    historyList.append(createVersionCard(version, "history"));
  });
}

function renderCacheState() {
  renderCurrentCache();
  renderHistory();
  reconcileDetailPane();
}

function selectedElementLabel(element) {
  const identity =
    element.visibleText ||
    element.id ||
    (element.classes || []).slice(0, 2).join(".") ||
    "";
  return [`'${element.reference}'`, element.tagName ? `<${element.tagName}>` : "", identity]
    .filter(Boolean)
    .join(" ");
}

function renderSelectedElements() {
  const elements = currentTabState.selectedElements || [];
  selectedElementsList.replaceChildren();
  selectedElementsList.hidden = !elements.length;

  elements.forEach((element) => {
    const chip = document.createElement("span");
    chip.className = "selected-element-chip";
    chip.title = selectedElementLabel(element);

    const label = document.createElement("span");
    label.textContent = selectedElementLabel(element);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.reference = element.reference;
    remove.setAttribute("aria-label", `Remove ${element.reference}`);
    remove.textContent = "x";

    chip.append(label, remove);
    selectedElementsList.append(chip);
  });
}

function removeReferenceFromPrompt(reference) {
  const escaped = reference.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const nextValue = promptInput.value
    .replace(new RegExp(`\\s*'?${escaped}'?`, "g"), " ")
    .replace(/\s{2,}/g, " ")
    .trim();
  setPromptValue(nextValue, { focus: document.activeElement === promptInput });
  syncPromptDraftFromInput();
}

async function removeSelectedReference(reference) {
  currentTabState.selectedElements = (currentTabState.selectedElements || []).filter(
    (element) => element.reference !== reference
  );
  const nextReference = nextElementReference(currentTabState.selectedElements);
  currentTabState.nextElementIndex = Number(nextReference.replace(/^element/, "")) || 1;
  removeReferenceFromPrompt(reference);
  renderSelectedElements();
  scheduleDraftSave();

  const tab = activeTab || (await getActiveTab().catch(() => null));
  if (tab?.id) {
    sendTabMessage(tab.id, { type: "FORGET_SELECTED_ELEMENT", reference }, 2000).catch(() => {});
  }
}

async function beginElementSelection() {
  const tab = activeTab || (await getActiveTab());
  await ensureContentScript(tab);
  syncPromptDraftFromInput();

  const nextReference = nextElementReference(currentTabState.selectedElements || []);
  currentTabState.nextElementIndex = Number(nextReference.replace(/^element/, "")) || 1;
  currentTabState.selectionMode = true;
  await persistTabState();

  const response = await sendRuntimeMessage(
    {
      type: "BEGIN_ELEMENT_SELECTION",
      payload: {
        tabId: tab.id,
        tabStateKey: activeTabKey,
        pageUrl: tab.url,
        pageKey: pageStateKey(tab),
        promptText: promptInput.value,
        selectionStart: promptInput.selectionStart || 0,
        selectionEnd: promptInput.selectionEnd || promptInput.selectionStart || 0,
        nextReference
      }
    },
    7000
  );

  if (response?.status === "error" || !response?.ok) {
    currentTabState.selectionMode = false;
    await persistTabState();
    throw new Error(response?.error?.message || "Could not start element selection.");
  }

  startElementPick.hidden = true;
  cancelElementPick.hidden = false;
  setComposerStatus("Click elements on the page. Press Escape when done.", "ready");
}

async function cancelElementSelection() {
  const tab = activeTab || (await getActiveTab());
  currentTabState.selectionMode = false;
  startElementPick.hidden = false;
  cancelElementPick.hidden = true;
  await persistTabState();
  await sendRuntimeMessage(
    { type: "CANCEL_ELEMENT_SELECTION", payload: { tabId: tab.id } },
    5000
  ).catch(() => {});
  setComposerStatus("Element selection cancelled.", "ready", true);
}

async function clearCurrentSiteCache() {
  let activeSiteKey = "";
  try {
    activeSiteKey = getSiteKey(activeTab?.url || "");
  } catch (_error) {
    activeSiteKey = "";
  }

  if (!activeSiteKey) {
    setComposerStatus("No website cache to clear on this tab.", "error", true);
    return;
  }

  clearAllPopupCache.disabled = true;
  clearAllPopupCache.textContent = "Clearing...";

  const data = await chrome.storage.local.get([HTML_CACHE_KEY, POPUP_TAB_STATE_KEY]);
  const cache = data[HTML_CACHE_KEY] || {};
  const store = data[POPUP_TAB_STATE_KEY] || {};

  Object.keys(cache).forEach((pageKey) => {
    try {
      if (getSiteKey(cache[pageKey]?.pageUrl || pageKey) === activeSiteKey) {
        delete cache[pageKey];
      }
    } catch (_error) {
      // Ignore malformed cache keys.
    }
  });

  Object.keys(store).forEach((stateKey) => {
    try {
      if (getSiteKey(stateKey) === activeSiteKey) {
        delete store[stateKey];
      }
    } catch (_error) {
      // Ignore non-URL tab fallback keys.
    }
  });

  await chrome.storage.local.set({
    [HTML_CACHE_KEY]: cache,
    [POPUP_TAB_STATE_KEY]: store
  });

  currentTabState = createEmptyTabState();
  setPromptValue("");
  collapseDetailPane();
  renderSelectedElements();
  renderCacheState();
  clearAllPopupCache.textContent = "Clear all";
  setComposerStatus("This site cache cleared.", "ready", true);
}

function createOriginalVersion(snapshotHtml, capturedAt = new Date(0).toISOString()) {
  return {
    id: createId(),
    index: 0,
    prompt: "",
    mode: null,
    kind: "original",
    createdAt: capturedAt,
    result: {
      modifiedHtml: snapshotHtml,
      patches: [],
      cssVars: {},
      cssRules: [],
      changesSummary: "Original page version",
      sourcePrompt: ""
    },
    pending: false
  };
}

function cacheEntryHasGeneratedOutput(entry) {
  return Boolean(
    entry?.modifiedHtml ||
      entry?.patches?.length ||
      Object.keys(entry?.cssVars || {}).length ||
      (entry?.cssRules || []).length
  );
}

function createGeneratedVersionFromCache(pageEntry) {
  return {
    id: createId(),
    index: 0,
    prompt: pageEntry.sourcePrompt || "",
    mode: normalizeMode(pageEntry.selectedMode),
    kind: "generated",
    createdAt: pageEntry.updatedAt || new Date().toISOString(),
    result: {
      modifiedHtml: pageEntry.modifiedHtml || "",
      patches: pageEntry.patches || [],
      cssVars: pageEntry.cssVars || {},
      cssRules: pageEntry.cssRules || [],
      apiResult: pageEntry.apiResult || {},
      changesSummary: pageEntry.changesSummary || "Cached page output",
      sourcePrompt: pageEntry.sourcePrompt || "",
      selectedMode: normalizeMode(pageEntry.selectedMode),
      traceId: pageEntry.traceId || "",
      pageIdentity: pageEntry.pageIdentity || {},
      pageSnapshot: pageEntry.pageSnapshot || {},
      editRecords: pageEntry.editRecords || [],
      deltaResult: pageEntry.deltaResult || null,
      parentVersionId: pageEntry.parentVersionId || null,
      mergeMode: pageEntry.mergeMode || "replace",
      mergeConflicts: pageEntry.mergeConflicts || [],
      mergeSummary: pageEntry.mergeSummary || null
    },
    deltaResult: pageEntry.deltaResult || null,
    parentVersionId: pageEntry.parentVersionId || null,
    mergeMode: pageEntry.mergeMode || "replace",
    pending: false
  };
}

async function ensureOriginalVersionFromHtmlCache(tab) {
  if (hasOriginalVersion(currentTabState)) {
    return false;
  }

  const data = await chrome.storage.local.get(HTML_CACHE_KEY);
  let pageEntry = null;
  try {
    pageEntry = data[HTML_CACHE_KEY]?.[getPageKey(tab.url || "")];
  } catch (_error) {
    pageEntry = null;
  }

  if (!pageEntry?.originalHtml) {
    return false;
  }

  currentTabState.history = [
    createOriginalVersion(pageEntry.originalHtml, pageEntry.originalCapturedAt || new Date(0).toISOString()),
    ...currentTabState.history
  ];
  currentTabState = renumberVersionIndexes(dedupeOriginalVersions(currentTabState));
  await persistTabState();
  return true;
}

async function ensureGeneratedVersionFromHtmlCache(tab) {
  if (hasGeneratedVersion(currentTabState)) {
    return false;
  }

  const data = await chrome.storage.local.get(HTML_CACHE_KEY);
  let pageEntry = null;
  try {
    pageEntry = data[HTML_CACHE_KEY]?.[getPageKey(tab.url || "")];
  } catch (_error) {
    pageEntry = null;
  }

  if (!cacheEntryHasGeneratedOutput(pageEntry)) {
    return false;
  }

  currentTabState.current = createGeneratedVersionFromCache(pageEntry);
  currentTabState = renumberVersionIndexes(dedupeOriginalVersions(currentTabState));
  await persistTabState();
  return true;
}

async function saveGeneratedVersion(prompt, mode, snapshotHtml, options = {}) {
  const versionId = createId();
  const baseVersion = Object.hasOwn(options, "baseVersion")
    ? options.baseVersion
    : currentTabState.current;
  const baseResult = cacheEntryHasGeneratedOutput(baseVersion?.result) ? baseVersion.result : null;
  const version = {
    id: versionId,
    index: 0,
    prompt,
    mode,
    kind: "generated",
    createdAt: new Date().toISOString(),
    result: null,
    deltaResult: null,
    baseResult,
    parentVersionId: baseResult ? baseVersion.id : null,
    mergeMode: baseResult ? "merge" : "replace",
    pending: true
  };

  let history = currentTabState.current
    ? [currentTabState.current, ...currentTabState.history]
    : currentTabState.history;

  if (!hasOriginalVersion(currentTabState)) {
    history = [createOriginalVersion(snapshotHtml), ...history];
  }

  currentTabState = renumberVersionIndexes({
    ...currentTabState,
    draftPrompt: "",
    draftMode: selectedMode,
    current: version,
    history: sortHistory(history)
  });

  setPromptValue("");
  renderSelectedElements();
  renderCacheState();
  await persistTabState();
  return versionId;
}

async function deleteCurrentVersion() {
  if (isOriginalVersion(currentTabState.current)) {
    throw new Error("Original save is protected.");
  }

  currentTabState.current = null;
  currentTabState = renumberVersionIndexes(currentTabState);
  renderCacheState();
  await persistTabState();
}

async function deleteHistoryVersion(versionId) {
  const selected = currentTabState.history.find((version) => version.id === versionId);

  if (isOriginalVersion(selected)) {
    throw new Error("Original save is protected.");
  }

  currentTabState.history = currentTabState.history.filter((version) => version.id !== versionId);
  currentTabState = renumberVersionIndexes(currentTabState);
  renderCacheState();
  await persistTabState();
}

// Rollback strategy, in priority order:
//   1. Original version → clear the page cache and reload the untouched site.
//   2. Version with a cached result → restore it via the background
//      ROLLBACK_TO_VERSION path (cache the result + reload; the content
//      script re-applies patches/css on the live page). This is the same
//      CSP-safe apply path a fresh generation uses, but costs no tokens.
//   3. No cached result → fall back to re-capturing the LIVE page and
//      re-running the version's prompt/mode through the normal pipeline
//      (the same path the Generate button uses).
// Replaying a stale full-DOM snapshot directly is intentionally avoided;
// the cache path applies surgical patches, not a script-reinjecting blob.
async function rollbackVersion(versionId) {
  const selected = currentTabState.history.find((version) => version.id === versionId);
  if (!selected) {
    return;
  }

  const tab = activeTab || (await getActiveTab());
  await ensureContentScript(tab);

  // The original has no prompt to re-run; "the real one" for it is the
  // genuine untouched page. Clear the page's mutable cache and reload so
  // the site loads with no patches applied (no stale snapshot replay).
  if (isOriginalVersion(selected)) {
    await sendTabMessage(tab.id, { type: "CLEAR_PAGE_CACHE" });

    // Keep the previously-current modified version in Templates — only the
    // live page resets to original, the saved versions must survive.
    const remaining = currentTabState.history.filter((version) => version.id !== versionId);
    const history = currentTabState.current
      ? [currentTabState.current, ...remaining]
      : remaining;
    currentTabState.current = selected;
    currentTabState.history = sortHistory(history);
    currentTabState = renumberVersionIndexes(currentTabState);
    renderCacheState();
    await persistTabState();
    await chrome.tabs.reload(tab.id);
    return;
  }

  // If this version already has a usable cached result, restore it directly
  // instead of re-running the model. This is the SAME apply path a fresh
  // generation uses (background caches the result, the tab reloads, the
  // content script applies patches/css on the live page) — so it's just as
  // CSP-safe as a normal generation, but free: no API call, no tokens spent.
  // Re-running is only worthwhile when there's no cached output to restore.
  if (cacheEntryHasGeneratedOutput(selected.result)) {
    const restore = await sendRuntimeMessage(
      {
        type: "ROLLBACK_TO_VERSION",
        payload: { tabId: tab.id, pageUrl: tab.url, version: selected }
      },
      7000
    );

    if (restore?.status === "error") {
      throw new Error(restore.error?.message || "Could not restore this version.");
    }
    if (!restore?.ok) {
      throw new Error("Background worker did not restore the version.");
    }

    // Make the restored version current and push the previously-current one
    // back into history — mirror the original-version branch so Templates
    // reflects reality instead of spawning a new box.
    const remaining = currentTabState.history.filter((version) => version.id !== versionId);
    const history = currentTabState.current
      ? [currentTabState.current, ...remaining]
      : remaining;
    currentTabState.current = selected;
    currentTabState.history = sortHistory(history);
    currentTabState = renumberVersionIndexes(currentTabState);
    renderCacheState();
    await persistTabState();
    setComposerStatus("Restored this version from cache — no tokens used.", "ready", true);
    return;
  }

  if (!selected.prompt && !selected.mode) {
    throw new Error("This version has no prompt to re-run.");
  }

  const snapshot = await sendTabMessage(tab.id, { type: "CAPTURE_PAGE_HTML" });
  if (snapshot.error) {
    throw new Error(snapshot.error);
  }
  if (resolveTokens(snapshot) > TOKEN_LIMIT) {
    throw new Error("This page is too large to send.");
  }

  // Don't let the shared save helper wipe the in-progress composer state.
  // The prompt draft and the selected mode are independent: a user can have
  // a mode chosen with no typed text, so each must be restored on its own —
  // gating the mode restore behind a non-empty draft silently erased it.
  const keptDraft = promptInput.value;
  const keptMode = selectedMode;

  const newVersionId = await saveGeneratedVersion(selected.prompt, selected.mode, snapshot.html, {
    baseVersion: selected
  });
  const pendingVersion = currentTabState.current;

  if (keptDraft) {
    setPromptValue(keptDraft);
    currentTabState.draftPrompt = keptDraft;
  }
  // Always re-apply the composer mode (independent of the prompt draft) so the
  // selection and its button UI survive the rollback re-run. setSelectedMode
  // also persists draftMode and schedules the draft save for us.
  setSelectedMode(keptMode);

  const handoff = await sendRuntimeMessage(
    {
      type: "START_PROCESS",
      payload: {
        tabId: tab.id,
        pageUrl: snapshot.pageUrl,
        html: snapshot.html,
        pageIdentity: snapshot.pageIdentity || getPageIdentity(snapshot.pageUrl),
        pageSnapshot: snapshot.pageSnapshot || null,
        promptVersionId: newVersionId,
        tabStateKey: activeTabKey,
        baseResult: pendingVersion?.baseResult || null,
        parentVersionId: pendingVersion?.parentVersionId || null,
        user_prompt: selected.prompt,
        selected_mode: selected.mode || null,
        params: { selected_elements: currentTabState.selectedElements || [] }
      }
    },
    7000
  );

  if (!handoff?.started) {
    throw new Error("Background worker did not start the job.");
  }

  setComposerStatus("Re-running this prompt on the live page…", "ready", true);
}

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local") {
    return;
  }

  if (!changes[POPUP_TAB_STATE_KEY] || !activeTabKey) {
    return;
  }

  const nextState = changes[POPUP_TAB_STATE_KEY].newValue?.[activeTabKey];
  if (!nextState) {
    return;
  }

  const normalized = normalizeTabState(nextState);
  const hasNewSelection =
    (normalized.selectedElements || []).length > (currentTabState.selectedElements || []).length;
  const shouldKeepLocalPrompt = hasLocalPromptActivity() && !hasNewSelection;

  if (shouldKeepLocalPrompt) {
    normalized.draftPrompt = promptInput.value;
    normalized.draftMode = currentTabState.draftMode;
    normalized.promptSelectionStart = promptInput.selectionStart || 0;
    normalized.promptSelectionEnd = promptInput.selectionEnd || normalized.promptSelectionStart;
    normalized.selectedElements = currentTabState.selectedElements || [];
    normalized.nextElementIndex = currentTabState.nextElementIndex || 1;
  }

  currentTabState = normalized;
  if (!shouldKeepLocalPrompt) {
    setPromptValue(currentTabState.draftPrompt, {
      selectionStart: currentTabState.promptSelectionStart,
      selectionEnd: currentTabState.promptSelectionEnd
    });
  }
  setSelectedMode(currentTabState.draftMode, false);
  startElementPick.hidden = currentTabState.selectionMode;
  cancelElementPick.hidden = !currentTabState.selectionMode;
  renderSelectedElements();
  renderCacheState();
});

function renderTabHeader(tab) {
  let urlText = tab.url || "";
  let titleText = tab.title || "Current tab";

  try {
    const parsedUrl = new URL(urlText);
    titleText = tab.title || parsedUrl.hostname || titleText;
    urlText = parsedUrl.href;
  } catch (_error) {
    // Keep Chrome-internal or otherwise unusual URLs as-is.
  }

  tabTitle.textContent = titleText;
  tabUrl.textContent = urlText;
  tabUrl.title = urlText;
}

async function loadTabState(tab) {
  activeTab = tab;
  activeTabKey = pageStateKey(tab);
  renderTabHeader(tab);

  const store = await getPopupStore();
  currentTabState = normalizeTabState(store[activeTabKey]);
  await ensureOriginalVersionFromHtmlCache(tab);
  await ensureGeneratedVersionFromHtmlCache(tab);
  setPromptValue(currentTabState.draftPrompt, {
    selectionStart: currentTabState.promptSelectionStart,
    selectionEnd: currentTabState.promptSelectionEnd
  });
  setSelectedMode(currentTabState.draftMode, false);
  startElementPick.hidden = currentTabState.selectionMode;
  cancelElementPick.hidden = !currentTabState.selectionMode;
  renderSelectedElements();
  renderCacheState();
}

// Mode buttons are created (with their click handlers) in renderModes().

promptInput.addEventListener("input", () => {
  syncPromptDraftFromInput();
  scheduleDraftSave();
});

["click", "keyup", "select"].forEach((eventName) => {
  promptInput.addEventListener(eventName, rememberPromptSelection);
});

historyToggle.addEventListener("click", async () => {
  currentTabState.historyExpanded = !currentTabState.historyExpanded;
  renderHistory();
  await persistTabState();
});

openSettings.addEventListener("click", async () => {
  await chrome.tabs.create({ url: chrome.runtime.getURL("options/options.html") });
  window.close();
});

clearAllPopupCache.addEventListener("click", () => {
  clearCurrentSiteCache().catch((error) => {
    clearAllPopupCache.disabled = false;
    clearAllPopupCache.textContent = "Clear all";
    setComposerStatus(error.message || "Could not clear cache.", "error", true);
  });
});

selectedElementsList.addEventListener("click", (event) => {
  const reference = event.target?.dataset?.reference;
  if (!reference) {
    return;
  }
  removeSelectedReference(reference).catch((error) => {
    setComposerStatus(error.message || "Could not remove selected element.", "error", true);
  });
});

startElementPick.addEventListener("click", () => {
  beginElementSelection().catch((error) => {
    startElementPick.hidden = false;
    cancelElementPick.hidden = true;
    setComposerStatus(error.message || "Could not start element selection.", "error", true);
  });
});

cancelElementPick.addEventListener("click", () => {
  cancelElementSelection().catch((error) => {
    setComposerStatus(error.message || "Could not cancel selection.", "error", true);
  });
});

currentCache.addEventListener("click", (event) => {
  const action = event.target?.dataset?.action;

  if (action === "delete-current") {
    deleteCurrentVersion().catch((error) => setComposerStatus(error.message || "Could not delete save.", "error", true));
  }
});

historyList.addEventListener("click", (event) => {
  const action = event.target?.dataset?.action;
  const versionId = event.target?.dataset?.versionId;

  if (!versionId) {
    return;
  }

  if (action === "rollback") {
    rollbackVersion(versionId).catch((error) => setComposerStatus(error.message || "Could not roll back.", "error", true));
  }

  if (action === "delete-history") {
    deleteHistoryVersion(versionId).catch((error) => setComposerStatus(error.message || "Could not delete save.", "error", true));
  }
});

applyPrompt.addEventListener("click", async () => {
  const userPrompt = promptInput.value.trim();
  const mode = selectedMode;

  // Frontend validates only what it can know: with no mode, a prompt is
  // required. The "mode has a blank instruction" case is backend-owned now
  // (instructions live server-side) and comes back as a clear EMPTY_PROMPT
  // error, surfaced via the normal error path below.
  if (!mode && !userPrompt) {
    setComposerStatus("Write a prompt or choose a mode first.", "error", true);
    promptInput.focus();
    return;
  }

  setGenerateBusy(true);
  setComposerStatus("Capturing the page...");

  try {
    const tab = activeTab || (await getActiveTab());
    await ensureContentScript(tab);
    const snapshot = await sendTabMessage(tab.id, { type: "CAPTURE_PAGE_HTML" });

    if (snapshot.error) {
      throw new Error(snapshot.error);
    }

    if (resolveTokens(snapshot) > TOKEN_LIMIT) {
      throw new Error("This page is too large to send.");
    }

    const versionId = await saveGeneratedVersion(userPrompt, mode, snapshot.html);
    const pendingVersion = currentTabState.current;
    // Send only the chosen mode key + the user prompt. The backend resolves
    // the mode's instruction and composes the effective prompt.
    const handoff = await sendRuntimeMessage(
      {
        type: "START_PROCESS",
        payload: {
          tabId: tab.id,
          pageUrl: snapshot.pageUrl,
          html: snapshot.html,
          pageIdentity: snapshot.pageIdentity || getPageIdentity(snapshot.pageUrl),
          pageSnapshot: snapshot.pageSnapshot || null,
          promptVersionId: versionId,
          tabStateKey: activeTabKey,
          baseResult: pendingVersion?.baseResult || null,
          parentVersionId: pendingVersion?.parentVersionId || null,
          user_prompt: userPrompt,
          selected_mode: mode || null,
          params: { selected_elements: currentTabState.selectedElements || [] }
        }
      },
      7000
    );

    if (!handoff?.started) {
      throw new Error("Background worker did not start the job.");
    }

    setComposerStatus("Queued. You can close this popup.", "ready", true);
  } catch (error) {
    setComposerStatus(error.message || "Something went wrong.", "error", true);
  } finally {
    setGenerateBusy(false);
  }
});

(async () => {
  try {
    const tab = await getActiveTab();
    await loadTabState(tab);
    loadModes().catch((error) => {
      setComposerStatus(
        `Couldn't load modes: ${error.message || "API unreachable"}.`,
        "error"
      );
    });
  } catch (error) {
    setComposerStatus(error.message || "Could not initialize popup.", "error");
  }
})();
