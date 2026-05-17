# DOM Patch Assistant

A Manifest V3 Chrome extension that lets you prompt a local AI API to modify the current page DOM.

## Current Flow

1. Open a normal website.
2. Open the extension popup.
3. Type a change request, for example: `move the sidebar to the top right`.
4. The extension captures the current page HTML and sends it to:
   `POST http://localhost:8000/api/v1/process`
5. The API returns DOM patches.
6. The content script applies the patches and caches them for the current page path.
7. When you reload that page later, cached patches are reapplied automatically.

## Files

- `manifest.json` - extension metadata, permissions, popup, background worker, and content script.
- `popup/` - prompt UI, health check, and clear-cache controls.
- `options/` - API base URL and enable/disable setting.
- `src/background.js` - calls `/api/v1/health` and `/api/v1/process`.
- `src/content.js` - captures page HTML, applies patches, and reapplies cached patches.
- `mock-api/server.js` - no-dependency mock API for local testing.
- `test-pages/selector-stability.html` - simple local page to try predictable patch targets.

## Load In Chrome

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click Load unpacked.
4. Select this folder: `C:\Users\anton\Desktop\ibm-extension`.

After editing extension files, click Reload on the extension card in `chrome://extensions`.

If the popup keeps showing an old status after code changes, close the popup, click Reload on the extension card, then reopen the popup. Chrome keeps old extension workers around until the extension is reloaded.

If you see `chrome.scripting` or `executeScript` errors, Chrome is still running an older copy of the manifest. Reload the extension in `chrome://extensions`, then refresh the website tab before using the popup again.

To use the local test page, enable Allow access to file URLs on the extension card, then open:
`C:\Users\anton\Desktop\ibm-extension\test-pages\selector-stability.html`

## Mock API

The mock API is a temporary local stand-in for the real backend.

Run it with:

```powershell
node mock-api\server.js
```

Health check:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/v1/health
```

If `node mock-api\server.js` says port `8000` is already in use, the mock API is probably already running. Use the health check above. To find the process:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
```

The mock returns simple patches for testing. Your real API can keep the same response shape:

```json
{
  "status": "ok",
  "result": {
    "patches": [
      {
        "op": "move",
        "selector": "#main-sidebar",
        "target_selector": "body",
        "position": "prepend"
      },
      {
        "op": "set_attr",
        "selector": "#main-sidebar",
        "name": "style",
        "value": "position: fixed; top: 20px; right: 20px;"
      }
    ]
  }
}
```

## Supported Patch Ops

- `move`
- `set_attr`
- `remove_attr`
- `set_text`
- `set_html`
- `set_style`
- `add_class`
- `remove_class`
- `insert_html`
- `remove`
- `delete`

## Notes

- Cached patches are keyed by `origin + pathname`, ignoring query string and hash.
- The content script adds `data-element-id` attributes before capture so the API can target elements like `[data-element-id="e5"]`.
- For dynamic pages, a mutation observer reapplies cached patches when new content appears.
- Chrome blocks content scripts on browser pages like `chrome://extensions`.
