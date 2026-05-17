// Runs in an offscreen document. Unlike the MV3 service worker, this context
// is not terminated on the ~30s idle timer, so a long /process request can
// complete here regardless of service-worker lifetime. The result is sent
// back via runtime messaging, which also wakes the worker if it was killed.

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "OFFSCREEN_FETCH") {
    return false;
  }

  performFetch(message);
  // Result is delivered via a separate OFFSCREEN_RESULT message, not a
  // response callback, so it survives a dead/respawned worker.
  return false;
});

async function performFetch({ requestId, url, body }) {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body
    });

    const text = await response.text();

    chrome.runtime.sendMessage({
      type: "OFFSCREEN_RESULT",
      requestId,
      ok: response.ok,
      httpStatus: response.status,
      body: text
    });
  } catch (error) {
    chrome.runtime.sendMessage({
      type: "OFFSCREEN_RESULT",
      requestId,
      error: error?.message || "Network request failed in offscreen document."
    });
  }
}
