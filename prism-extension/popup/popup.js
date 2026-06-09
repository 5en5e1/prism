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

const TOKEN_LIMIT = 1000000;
const CHARS_PER_TOKEN = 4;
const POPUP_TAB_STATE_KEY = "popupTabPromptState";
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

function createEmptyTabState() {
  return {
    draftPrompt: "",
    draftMode: null,
    current: null,
    history: [],
    nextIndex: 1,
    historyExpanded: false
  };
}

function normalizeTabState(state = {}) {
  return renumberVersionIndexes({
    ...createEmptyTabState(),
    ...state,
    draftMode: normalizeMode(state.draftMode),
    current: normalizeVersion(state.current),
    history: Array.isArray(state.history) ? state.history.map(normalizeVersion).filter(Boolean) : [],
    nextIndex: Number.isInteger(state.nextIndex) && state.nextIndex > 0 ? state.nextIndex : 1,
    historyExpanded: Boolean(state.historyExpanded)
  });
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
    pending: Boolean(version.pending)
  };
}

function normalizeMode(mode) {
  if (mode == null) return null;
  // Tolerate old numeric/persisted values; any key not in the backend's
  // mode list (retired/unknown) resolves to no mode.
  const legacyNumeric = { 1: "focus", 2: "modernization", 3: "mode3", 4: "mode4" };
  const key = Object.hasOwn(legacyNumeric, mode) ? legacyNumeric[mode] : mode;
  return knownModeKeys().has(key) ? key : null;
}

function createId() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
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

async function refreshTabStateFromStorage() {
  if (!activeTabKey) {
    return;
  }

  const store = await getPopupStore();
  currentTabState = normalizeTabState(store[activeTabKey]);
  promptInput.value = currentTabState.draftPrompt;
  setSelectedMode(currentTabState.draftMode, false);
  renderCacheState();
}

function scheduleDraftSave() {
  if (!activeTabKey) {
    return;
  }

  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
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

function createDetailPopout(version) {
  const detail = document.createElement("div");
  detail.className = "detail-popout";

  const prompt = version.prompt.trim();
  const detailText = document.createElement("p");
  detailText.className = "detail-text";

  if (version.kind === "original") {
    detailText.textContent = "Original page version captured before the first generated change.";
    detail.append(detailText);
  } else if (prompt) {
    detailText.textContent = prompt;
    detail.append(detailText);
  } else if (version.pending) {
    detailText.textContent = "This generated version is still waiting for the API result.";
    detail.append(detailText);
  }

  if (version.mode) {
    const badge = document.createElement("span");
    badge.className = "mode-badge";
    badge.textContent = modeLabel(version.mode);
    detail.append(badge);
  }

  return detail;
}

function isRollbackable(version) {
  const result = version?.result;
  return Boolean(
    result?.modifiedHtml ||
      result?.patches?.length ||
      Object.keys(result?.cssVars || {}).length ||
      result?.cssRules?.length
  );
}

function createVersionCard(version, placement) {
  const card = document.createElement("article");
  card.className = `version-card ${placement === "current" ? "current-card" : "history-card"}`;
  card.dataset.versionId = version.id;
  card.tabIndex = 0;

  card.append(createTextElement("version-index", `#${version.index}`));
  card.append(createTextElement("version-preview", previewVersion(version)));

  if (placement === "current") {
    card.append(createTextElement("current-chip", "Current"));
  }

  if (placement === "history") {
    const rollbackButton = document.createElement("button");
    rollbackButton.className = "version-action";
    rollbackButton.type = "button";
    rollbackButton.dataset.action = "rollback";
    rollbackButton.dataset.versionId = version.id;
    rollbackButton.disabled = version.pending || !isRollbackable(version);
    rollbackButton.textContent = "Rollback";
    card.append(rollbackButton);
  }

  const deleteButton = document.createElement("button");
  deleteButton.className = "version-action danger";
  deleteButton.type = "button";
  deleteButton.dataset.action = placement === "history" ? "delete-history" : "delete-current";
  deleteButton.dataset.versionId = version.id;
  deleteButton.textContent = "Delete";
  card.append(deleteButton);

  card.append(createDetailPopout(version));
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
  historyArrow.textContent = expanded ? "v" : ">";
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
}

function createOriginalVersion(snapshotHtml) {
  return {
    id: createId(),
    index: 0,
    prompt: "",
    mode: null,
    kind: "original",
    createdAt: new Date(0).toISOString(),
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

async function saveGeneratedVersion(prompt, mode, snapshotHtml) {
  const versionId = createId();
  const version = {
    id: versionId,
    index: 0,
    prompt,
    mode,
    kind: "generated",
    createdAt: new Date().toISOString(),
    result: null,
    pending: true
  };

  let history = currentTabState.current
    ? [currentTabState.current, ...currentTabState.history]
    : currentTabState.history;

  if (!currentTabState.current && !currentTabState.history.length) {
    history = [createOriginalVersion(snapshotHtml), ...history];
  }

  currentTabState = renumberVersionIndexes({
    ...currentTabState,
    draftPrompt: "",
    draftMode: selectedMode,
    current: version,
    history: sortHistory(history)
  });

  promptInput.value = "";
  renderCacheState();
  await persistTabState();
  return versionId;
}

async function deleteCurrentVersion() {
  currentTabState.current = null;
  currentTabState = renumberVersionIndexes(currentTabState);
  renderCacheState();
  await persistTabState();
}

async function deleteHistoryVersion(versionId) {
  currentTabState.history = currentTabState.history.filter((version) => version.id !== versionId);
  currentTabState = renumberVersionIndexes(currentTabState);
  renderCacheState();
  await persistTabState();
}

async function rollbackVersion(versionId) {
  const selected = currentTabState.history.find((version) => version.id === versionId);
  if (!selected) {
    return;
  }

  if (!isRollbackable(selected)) {
    throw new Error("This version is not ready yet.");
  }

  const response = await sendRuntimeMessage(
    {
      type: "ROLLBACK_TO_VERSION",
      payload: {
        tabId: activeTab.id,
        pageUrl: activeTab.url,
        version: selected
      }
    },
    7000
  );

  if (!response?.ok) {
    throw new Error(response?.error?.message || "Could not roll back page.");
  }

  const remaining = currentTabState.history.filter((version) => version.id !== versionId);
  const history = currentTabState.current ? [currentTabState.current, ...remaining] : remaining;

  currentTabState.current = selected;
  currentTabState.history = sortHistory(history);
  currentTabState = renumberVersionIndexes(currentTabState);
  renderCacheState();
  await persistTabState();
}

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes[POPUP_TAB_STATE_KEY] || !activeTabKey) {
    return;
  }

  const nextState = changes[POPUP_TAB_STATE_KEY].newValue?.[activeTabKey];
  if (!nextState) {
    return;
  }

  currentTabState = normalizeTabState(nextState);
  promptInput.value = currentTabState.draftPrompt;
  setSelectedMode(currentTabState.draftMode, false);
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
  activeTabKey = String(tab.id);
  renderTabHeader(tab);

  const store = await getPopupStore();
  currentTabState = normalizeTabState(store[activeTabKey]);
  promptInput.value = currentTabState.draftPrompt;
  setSelectedMode(currentTabState.draftMode, false);
  renderCacheState();
}

// Mode buttons are created (with their click handlers) in renderModes().

promptInput.addEventListener("input", () => {
  currentTabState.draftPrompt = promptInput.value;
  currentTabState.draftMode = selectedMode;
  scheduleDraftSave();
});

historyToggle.addEventListener("click", async () => {
  currentTabState.historyExpanded = !currentTabState.historyExpanded;
  renderHistory();
  await persistTabState();
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
    // Send only the chosen mode key + the user prompt. The backend resolves
    // the mode's instruction and composes the effective prompt.
    const handoff = await sendRuntimeMessage(
      {
        type: "START_PROCESS",
        payload: {
          tabId: tab.id,
          pageUrl: snapshot.pageUrl,
          html: snapshot.html,
          promptVersionId: versionId,
          tabStateKey: activeTabKey,
          user_prompt: userPrompt,
          selected_mode: mode || null,
          params: {}
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
    // Render modes (from the backend) before restoring tab state so a
    // persisted mode selection can be re-applied to real buttons.
    await loadModes();
    const tab = await getActiveTab();
    await loadTabState(tab);
  } catch (error) {
    setComposerStatus(error.message || "Could not initialize popup.", "error");
  }
})();
