const enabledInput = document.querySelector("#enabled");
const apiBaseUrlInput = document.querySelector("#apiBaseUrl");
const saveState = document.querySelector("#saveState");

async function loadSettings() {
  const { settings = { apiBaseUrl: "http://localhost:8000", enabled: true } } = await chrome.storage.local.get("settings");
  apiBaseUrlInput.value = settings.apiBaseUrl || "http://localhost:8000";
  enabledInput.checked = Boolean(settings.enabled);
}

async function saveSettings() {
  await chrome.storage.local.set({
    settings: {
      apiBaseUrl: apiBaseUrlInput.value.trim() || "http://localhost:8000",
      enabled: enabledInput.checked
    }
  });

  saveState.textContent = "Saved";
  window.setTimeout(() => {
    saveState.textContent = "";
  }, 1400);
}

apiBaseUrlInput.addEventListener("change", saveSettings);
enabledInput.addEventListener("change", saveSettings);

loadSettings();
