const API_HEALTH_TIMEOUT_MS = 4000;

const HTML_CACHE_KEY = "domHtmlCache";
const JOB_STATUS_KEY = "lastJob";
const PENDING_JOBS_KEY = "pendingJobs";
const POPUP_TAB_STATE_KEY = "popupTabPromptState";
const MAX_CACHED_PAGES = 20;
const OFFSCREEN_PATH = "offscreen.html";

// MV3 terminates an idle service worker after ~30s. A long fetch that is not
// bound to an unanswered message event does NOT keep it alive on its own, so
// we ping a chrome API every 20s while a job runs to reset the idle timer.
const KEEPALIVE_INTERVAL_MS = 20000;
let keepAliveTimer = null;
let activeJobCount = 0;

function startKeepAlive() {
  activeJobCount += 1;
  if (keepAliveTimer !== null) {
    return;
  }
  keepAliveTimer = setInterval(() => {
    chrome.runtime.getPlatformInfo(() => void chrome.runtime.lastError);
  }, KEEPALIVE_INTERVAL_MS);
}

function stopKeepAlive() {
  activeJobCount = Math.max(0, activeJobCount - 1);
  if (activeJobCount === 0 && keepAliveTimer !== null) {
    clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }
}

chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === "install") {
    chrome.storage.local.set({
      settings: {
        apiBaseUrl: "http://localhost:8000/",
        enabled: true
      }
    });
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.get(POPUP_TAB_STATE_KEY).then((data) => {
    const tabState = data[POPUP_TAB_STATE_KEY] || {};

    if (!tabState[String(tabId)]) {
      return;
    }

    delete tabState[String(tabId)];
    chrome.storage.local.set({ [POPUP_TAB_STATE_KEY]: tabState });
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "PING_EXTENSION") {
    sendResponse({ ok: true, receivedAt: Date.now() });
    return true;
  }

  if (message?.type === "CHECK_API_HEALTH") {
    checkApiHealth()
      .then(sendResponse)
      .catch((error) => sendResponse(toErrorResponse(error)));
    return true;
  }

  if (message?.type === "FETCH_MODES") {
    fetchModes()
      .then((modes) => sendResponse({ ok: true, modes }))
      .catch((error) => sendResponse(toErrorResponse(error)));
    return true;
  }

  if (message?.type === "START_PROCESS") {
    // Acknowledge immediately so the popup can close / the user can switch
    // tabs. The fetch runs in the offscreen document and the result comes
    // back as OFFSCREEN_RESULT, independent of the popup or worker lifetime.
    startProcessJob(message.payload)
      .then(() => sendResponse({ ok: true, started: true }))
      .catch((error) => sendResponse(toErrorResponse(error)));
    return true;
  }

  if (message?.type === "ROLLBACK_TO_VERSION") {
    rollbackToVersion(message.payload)
      .then(sendResponse)
      .catch((error) => sendResponse(toErrorResponse(error)));
    return true;
  }

  if (message?.type === "OFFSCREEN_RESULT") {
    finalizeJob(message);
    return false;
  }

  if (message?.type === "GET_JOB_STATUS") {
    chrome.storage.local
      .get(JOB_STATUS_KEY)
      .then((data) => sendResponse(data[JOB_STATUS_KEY] || null));
    return true;
  }

  return false;
});

function getPageKey(url) {
  const parsedUrl = new URL(url);
  return `${parsedUrl.origin}${parsedUrl.pathname}`;
}

async function setJobStatus(state, message, extra = {}) {
  const status = { state, message, updatedAt: new Date().toISOString(), ...extra };
  await chrome.storage.local.set({ [JOB_STATUS_KEY]: status });

  const badge = { processing: "…", done: "✓", error: "!" }[state] || "";
  try {
    await chrome.action.setBadgeText({ text: badge });
    await chrome.action.setBadgeBackgroundColor({
      color: state === "error" ? "#dc2626" : "#2563eb"
    });
  } catch (_error) {
    // Badge is cosmetic; never let it break the job.
  }
}

function notify(title, message) {
  try {
    chrome.notifications.create({
      type: "basic",
      iconUrl:
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
      title,
      message: message.slice(0, 240)
    });
  } catch (_error) {
    // Notifications are best-effort.
  }
}

async function cachePageResult(pageUrl, entry) {
  const pageKey = getPageKey(pageUrl);
  const data = await chrome.storage.local.get(HTML_CACHE_KEY);
  const cache = data[HTML_CACHE_KEY] || {};

  cache[pageKey] = {
    pageUrl,
    updatedAt: new Date().toISOString(),
    ...entry
  };

  const keys = Object.keys(cache);
  if (keys.length > MAX_CACHED_PAGES) {
    keys
      .sort((a, b) => (cache[a]?.updatedAt || "").localeCompare(cache[b]?.updatedAt || ""))
      .slice(0, keys.length - MAX_CACHED_PAGES)
      .forEach((key) => delete cache[key]);
  }

  await chrome.storage.local.set({ [HTML_CACHE_KEY]: cache });
}

function resultToCacheEntry(versionResult, version = {}) {
  return {
    patches: versionResult?.patches || [],
    cssVars: versionResult?.cssVars || {},
    cssRules: versionResult?.cssRules || [],
    modifiedHtml: versionResult?.modifiedHtml || "",
    apiResult: versionResult?.apiResult || {},
    sourcePrompt: version.prompt || "",
    selectedMode: version.mode || null,
    changesSummary: versionResult?.changesSummary || "",
    traceId: versionResult?.traceId || ""
  };
}

async function rollbackToVersion(payload) {
  const { tabId, pageUrl, version } = payload || {};

  if (!pageUrl || !version?.result) {
    throw new Error("Rollback version is missing page data.");
  }

  const result = version.result;
  const hasPageResult =
    Boolean(result.modifiedHtml) ||
    Boolean(result.patches?.length) ||
    Boolean(Object.keys(result.cssVars || {}).length) ||
    Boolean(result.cssRules?.length);

  if (!hasPageResult) {
    throw new Error("This version does not contain a page layout to restore.");
  }

  await cachePageResult(pageUrl, resultToCacheEntry(version.result, version));
  await redirectToOutput(tabId, pageUrl);
  return { ok: true };
}

async function updatePopupVersionResult(tabStateKey, versionId, result) {
  if (!tabStateKey || !versionId) {
    return;
  }

  const data = await chrome.storage.local.get(POPUP_TAB_STATE_KEY);
  const tabState = data[POPUP_TAB_STATE_KEY] || {};
  const state = tabState[tabStateKey];

  if (!state) {
    return;
  }

  const updateVersion = (version) => {
    if (!version || version.id !== versionId) {
      return version;
    }

    return {
      ...version,
      result,
      pending: false
    };
  };

  state.current = updateVersion(state.current);
  state.history = Array.isArray(state.history) ? state.history.map(updateVersion) : [];
  tabState[tabStateKey] = state;
  await chrome.storage.local.set({ [POPUP_TAB_STATE_KEY]: tabState });
}

// Bring the user to the scraped URL. The content script auto-applies the
// cached modified HTML on that page load, so this works even if the popup
// closed, the user switched tabs, or navigated the original tab away.
async function redirectToOutput(tabId, pageUrl) {
  let tab = null;

  if (typeof tabId === "number") {
    tab = await chrome.tabs.get(tabId).catch(() => null);
  }

  if (tab) {
    if (tab.url === pageUrl) {
      await chrome.tabs.reload(tabId);
      await chrome.tabs.update(tabId, { active: true });
    } else {
      await chrome.tabs.update(tabId, { url: pageUrl, active: true });
    }

    if (typeof tab.windowId === "number") {
      await chrome.windows.update(tab.windowId, { focused: true }).catch(() => {});
    }
    return;
  }

  await chrome.tabs.create({ url: pageUrl, active: true });
}

let offscreenSetup = null;

async function ensureOffscreenDocument() {
  if (await chrome.offscreen.hasDocument().catch(() => false)) {
    return;
  }

  // Guard against parallel creation (one offscreen document is allowed).
  if (!offscreenSetup) {
    offscreenSetup = chrome.offscreen
      .createDocument({
        url: OFFSCREEN_PATH,
        reasons: ["WORKERS"],
        justification: "Run the long /process API request outside the killable service worker."
      })
      .catch((error) => {
        // "Only a single offscreen document" means it already exists — fine.
        if (!String(error?.message || "").includes("single offscreen")) {
          throw error;
        }
      })
      .finally(() => {
        offscreenSetup = null;
      });
  }

  await offscreenSetup;
}

async function closeOffscreenIfIdle() {
  const data = await chrome.storage.local.get(PENDING_JOBS_KEY);
  const pending = data[PENDING_JOBS_KEY] || {};

  if (Object.keys(pending).length > 0) {
    return;
  }

  if (await chrome.offscreen.hasDocument().catch(() => false)) {
    await chrome.offscreen.closeDocument().catch(() => {});
  }
}

async function savePendingJob(requestId, job) {
  const data = await chrome.storage.local.get(PENDING_JOBS_KEY);
  const pending = data[PENDING_JOBS_KEY] || {};
  pending[requestId] = job;
  await chrome.storage.local.set({ [PENDING_JOBS_KEY]: pending });
}

async function takePendingJob(requestId) {
  const data = await chrome.storage.local.get(PENDING_JOBS_KEY);
  const pending = data[PENDING_JOBS_KEY] || {};
  const job = pending[requestId];
  delete pending[requestId];
  await chrome.storage.local.set({ [PENDING_JOBS_KEY]: pending });
  return job || null;
}

async function startProcessJob(payload) {
  const { tabId, pageUrl } = payload;
  const requestId = crypto.randomUUID();
  const traceId = crypto.randomUUID();
  const settings = await getSettings();

  startKeepAlive();

  await savePendingJob(requestId, {
    tabId,
    pageUrl,
    promptVersionId: payload.promptVersionId || "",
    tabStateKey: payload.tabStateKey || "",
    userPrompt: payload.user_prompt || "",
    selectedMode: payload.selected_mode || null,
    createdAt: new Date().toISOString()
  });

  await setJobStatus("processing", "Sending page to the API and waiting for a response…", {
    pageUrl
  });

  // Mirrors the backend ProcessRequest contract exactly. user_prompt is a
  // string ("" when only a mode is used); selected_mode is null or a known
  // key. The backend resolves the instruction from the key — no instruction
  // text is sent.
  const requestBody = JSON.stringify({
    page_url: pageUrl,
    html: payload.html,
    user_prompt: payload.user_prompt || "",
    selected_mode: payload.selected_mode || null,
    params: payload.params || {},
    client_metadata: {
      extension_version: chrome.runtime.getManifest().version,
      trace_id: traceId
    }
  });

  try {
    await ensureOffscreenDocument();
    await chrome.runtime.sendMessage({
      type: "OFFSCREEN_FETCH",
      requestId,
      url: joinUrl(settings.apiBaseUrl, "/api/v1/process"),
      body: requestBody
    });
  } catch (error) {
    await takePendingJob(requestId);
    await setJobStatus("error", error.message || "Could not start the request.", { pageUrl });
    notify("Prism failed", error.message || "Could not start the request.");
    stopKeepAlive();
    await closeOffscreenIfIdle();
    throw error;
  }
}

// Handles the result that the offscreen document sends back. Runs even if the
// service worker was killed mid-fetch (the message wakes it back up).
async function finalizeJob(message) {
  const job = await takePendingJob(message.requestId);

  if (!job) {
    // Unknown/duplicate result — nothing to finalize.
    stopKeepAlive();
    await closeOffscreenIfIdle();
    return;
  }

  const {
    tabId,
    pageUrl,
    promptVersionId,
    tabStateKey,
    userPrompt,
    selectedMode
  } = job;

  try {
    if (message.error) {
      throw new Error(message.error);
    }

    let data = null;
    try {
      data = JSON.parse(message.body);
    } catch (_error) {
      data = null;
    }

    if (!message.ok) {
      throw new Error(
        data?.error?.message || `API request failed with HTTP ${message.httpStatus}.`
      );
    }

    if (!data) {
      throw new Error("API returned a response that could not be parsed as JSON.");
    }

    if (data.status === "error") {
      throw new Error(data.error?.message || "API returned an error.");
    }

    if (data.status !== "ok" && data.status !== "partial") {
      throw new Error(`API returned unexpected status "${data.status}".`);
    }

    const patches = data.result?.patches || [];
    const cssVars = data.result?.css_vars || {};
    const cssRules = data.result?.css_rules || [];
    const modifiedHtml = data.result?.modified_html || "";
    const canApplyToPage =
      Boolean(modifiedHtml) || patches.length || Object.keys(cssVars).length || cssRules.length;

    if (!canApplyToPage) {
      throw new Error("API response contained no page changes to apply.");
    }

    const changesSummary =
      data.result?.changes_summary ||
      data.result?.changes_made?.join?.(", ") ||
      (data.result?.summary ? data.result.summary : "");

    const versionResult = {
      patches,
      cssVars,
      cssRules,
      modifiedHtml,
      apiResult: data.result || {},
      sourcePrompt: userPrompt,
      selectedMode,
      changesSummary,
      traceId: data.trace_id || ""
    };

    await cachePageResult(pageUrl, versionResult);
    await updatePopupVersionResult(tabStateKey, promptVersionId, versionResult);

    if (canApplyToPage) {
      await redirectToOutput(tabId, pageUrl);
    }

    const partialNote = data.status === "partial" ? " (partial result)" : "";
    await setJobStatus("done", `Done${partialNote}. ${changesSummary}`.trim(), { pageUrl });
    notify("Prism done", `${changesSummary || "Changes applied."} ${pageUrl}`);
  } catch (error) {
    const errorMessage = error.message || "Processing failed.";
    await setJobStatus("error", errorMessage, { pageUrl });
    notify("Prism failed", errorMessage);
  } finally {
    stopKeepAlive();
    await closeOffscreenIfIdle();
  }
}

async function getSettings() {
  const { settings = {} } = await chrome.storage.local.get("settings");

  return {
    apiBaseUrl: settings.apiBaseUrl || "http://localhost:8000",
    enabled: settings.enabled !== false
  };
}

function joinUrl(baseUrl, path) {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function checkApiHealth() {
  const settings = await getSettings();
  const response = await fetchWithTimeout(
    joinUrl(settings.apiBaseUrl, "/api/v1/health"),
    {},
    API_HEALTH_TIMEOUT_MS
  );

  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}.`);
  }

  return response.json();
}

const MODES_CACHE_KEY = "cachedModes";

// Backend is the source of truth for modes. Fetch {key,label} list; cache it
// so the popup still renders if the API is briefly unreachable. On total
// failure (never fetched) return [] -> popup shows "no modes".
async function fetchModes() {
  const settings = await getSettings();
  try {
    const response = await fetchWithTimeout(
      joinUrl(settings.apiBaseUrl, "/api/v1/modes"),
      {},
      API_HEALTH_TIMEOUT_MS
    );
    if (!response.ok) {
      throw new Error(`Modes fetch failed with HTTP ${response.status}.`);
    }
    const data = await response.json();
    const modes = Array.isArray(data?.modes) ? data.modes : [];
    await chrome.storage.local.set({ [MODES_CACHE_KEY]: modes });
    return modes;
  } catch (error) {
    const cached = await chrome.storage.local.get(MODES_CACHE_KEY);
    if (Array.isArray(cached[MODES_CACHE_KEY])) {
      return cached[MODES_CACHE_KEY];
    }
    throw error;
  }
}

async function fetchWithTimeout(url, options, timeoutMs) {
  // timeoutMs <= 0 means "no timeout": wait until the server responds.
  if (!timeoutMs || timeoutMs <= 0) {
    return fetch(url, options);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`API request timed out after ${Math.round(timeoutMs / 1000)}s: ${url}`);
    }

    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

function toErrorResponse(error) {
  return {
    status: "error",
    error: {
      code: "EXTENSION_ERROR",
      message: error.message || "Unknown extension error.",
      retryable: false,
      stage: "extension"
    }
  };
}
