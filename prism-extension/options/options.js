const cacheState = document.querySelector("#cacheState");
const cacheList = document.querySelector("#cacheList");
const cacheEmpty = document.querySelector("#cacheEmpty");
const clearAllCache = document.querySelector("#clearAllCache");
const enabledInput = document.querySelector("#enabled");
const apiBaseUrlInput = document.querySelector("#apiBaseUrl");
const saveState = document.querySelector("#saveState");

const HTML_CACHE_KEY = "domHtmlCache";
const POPUP_TAB_STATE_KEY = "popupTabPromptState";
const JOB_STATUS_KEY = "lastJob";
const PENDING_JOBS_KEY = "pendingJobs";
const MODES_CACHE_KEY = "cachedModes";
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function showCacheState(message) {
  cacheState.textContent = message;
  window.clearTimeout(showCacheState.timer);
  showCacheState.timer = window.setTimeout(() => {
    cacheState.textContent = "";
  }, 1600);
}

function showSaveState(message) {
  saveState.textContent = message;
  window.clearTimeout(showSaveState.timer);
  showSaveState.timer = window.setTimeout(() => {
    saveState.textContent = "";
  }, 1600);
}

async function loadSettings() {
  const { settings = {} } = await chrome.storage.local.get("settings");
  apiBaseUrlInput.value = settings.apiBaseUrl || DEFAULT_API_BASE_URL;
  enabledInput.checked = settings.enabled !== false;
}

async function saveSettings() {
  await chrome.storage.local.set({
    settings: {
      apiBaseUrl: apiBaseUrlInput.value.trim() || DEFAULT_API_BASE_URL,
      enabled: enabledInput.checked
    }
  });
  showSaveState("Saved");
}

function formatDate(value) {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) {
    return "Unknown time";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function displayUrl(url) {
  try {
    const parsed = new URL(url);
    return {
      title: parsed.hostname,
      detail: `${parsed.pathname || "/"}${parsed.search || ""}`
    };
  } catch (_error) {
    return { title: url || "Unknown page", detail: "" };
  }
}

function hasGeneratedOutput(entry) {
  return Boolean(
    entry?.modifiedHtml ||
      entry?.patches?.length ||
      Object.keys(entry?.cssVars || {}).length ||
      (entry?.cssRules || []).length
  );
}

function createCacheCard([pageKey, entry]) {
  const url = entry?.pageUrl || pageKey;
  const { title, detail } = displayUrl(url);
  const generated = hasGeneratedOutput(entry);
  const patchCount = (entry?.patches || []).length;
  const ruleCount = (entry?.cssRules || []).length;

  const card = document.createElement("button");
  card.type = "button";
  card.className = "cache-card";
  card.dataset.url = url;

  const meta = document.createElement("span");
  meta.className = "cache-meta";

  const titleEl = document.createElement("strong");
  titleEl.textContent = title;

  const detailEl = document.createElement("small");
  detailEl.textContent = detail || url;
  detailEl.title = url;

  meta.append(titleEl, detailEl);

  const stats = document.createElement("span");
  stats.className = "cache-stats";

  const state = document.createElement("span");
  state.className = generated ? "status-pill generated" : "status-pill original";
  state.textContent = generated ? "Generated" : "Original only";

  const summary = document.createElement("span");
  summary.className = "cache-summary";
  summary.textContent = [
    patchCount ? `${patchCount} patches` : "",
    ruleCount ? `${ruleCount} rules` : "",
    entry?.modifiedHtml ? "full HTML" : "",
    `updated ${formatDate(entry?.updatedAt || entry?.originalCapturedAt)}`
  ]
    .filter(Boolean)
    .join(" / ");

  stats.append(state, summary);
  card.append(meta, stats);
  return card;
}

async function loadCacheList() {
  const data = await chrome.storage.local.get(HTML_CACHE_KEY);
  const cache = data[HTML_CACHE_KEY] || {};
  const entries = Object.entries(cache).sort((a, b) =>
    (b[1]?.updatedAt || b[1]?.originalCapturedAt || "").localeCompare(
      a[1]?.updatedAt || a[1]?.originalCapturedAt || ""
    )
  );

  cacheList.replaceChildren(...entries.map(createCacheCard));
  cacheEmpty.hidden = entries.length > 0;
}

async function clearEverything() {
  clearAllCache.disabled = true;
  clearAllCache.textContent = "Clearing...";

  await chrome.storage.local.remove([
    HTML_CACHE_KEY,
    POPUP_TAB_STATE_KEY,
    JOB_STATUS_KEY,
    PENDING_JOBS_KEY,
    MODES_CACHE_KEY
  ]);

  try {
    await chrome.action.setBadgeText({ text: "" });
  } catch (_error) {
    // Badge cleanup is cosmetic.
  }

  await loadCacheList();
  showCacheState("Cache cleared");
  clearAllCache.disabled = false;
  clearAllCache.textContent = "Clear everything";
}

cacheList.addEventListener("click", async (event) => {
  const card = event.target.closest(".cache-card");
  const url = card?.dataset?.url;
  if (!url) {
    return;
  }

  await chrome.tabs.create({ url, active: true });
});

clearAllCache.addEventListener("click", () => {
  clearEverything().catch((error) => {
    showCacheState(error.message || "Could not clear cache");
    clearAllCache.disabled = false;
    clearAllCache.textContent = "Clear everything";
  });
});

apiBaseUrlInput.addEventListener("change", saveSettings);
enabledInput.addEventListener("change", saveSettings);

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes[HTML_CACHE_KEY]) {
    loadCacheList().catch(() => {});
  }
});

loadSettings();
loadCacheList();
