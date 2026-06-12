# Prism

Prism is a Chrome extension plus local backend for changing live webpages with AI-assisted DOM patches. The project is not production-ready yet, but this version is a much better foundation than the original prototype: the main flow now works end to end, the UI is cleaner, templates are owned by the backend, and users can point the AI at exact page elements by clicking them.

## Current Status

We successfully completed the current rebuild steps:

- Backend-configured templates are available through `/api/v1/modes`.
- The popup can fetch and apply state-of-the-art prompt templates such as Modern, Futuristic, Cartoon, and Solarpunk.
- Users can click page elements, reference them in the prompt, and ask the AI to modify those exact elements.
- Element selection now supports deselection and does not duplicate the same element.
- Saves/history are available in the popup, with restore and delete actions.
- The popup UI was improved with a slide-out detail pane for saves and templates.
- Page outputs are cached locally so the extension can re-apply saved changes.

This is still an active development build. It is not ready for production distribution, but it is now a better and more practical version of the product direction.

## What Prism Does

Prism lets a user open the extension on a webpage, write a prompt, optionally choose a backend template, and generate changes for the current page.

The important workflow is:

1. Open a normal webpage.
2. Open the Prism extension.
3. Optionally click `Pick` and select elements on the page.
4. Write a prompt that references selected elements, for example: `make 'element1' look like a floating glass card`.
5. Choose a template if useful.
6. Generate the change.
7. Restore or delete saved versions from the popup.

## Templates

Templates live in the backend, not in the extension UI. The extension fetches the available templates from:

```text
GET /api/v1/modes
```

Template prompt files are stored here:

```text
backend/app/prompts/modes/
```

Current examples include:

- `modern.md`
- `futuristic.md`
- `cartoon.md`
- `solarpunk.md`

This makes templates easy to change without rebuilding the extension. The popup only sends the selected template key; the backend resolves the actual instruction.

## Element References

Prism can reference exact page elements. When the user clicks `Pick`, the content script overlays the page and records rich metadata for selected elements:

- stable selector candidates
- DOM path
- visible text
- tag name, id, classes, data attributes, and useful attributes
- bounding box and visual position
- selected computed styles
- nearby DOM context
- a fingerprint used for matching and deselection

The selected element becomes a prompt token such as:

```text
'element1'
```

That token is stored with the element metadata and sent to the backend. This lets the model understand that the user is talking about a specific live element, not a vague region of the page.

## How The Low-Cost Patch Flow Works

The expensive naive approach is to send a model the raw HTML of a page and ask it to return a modified full document. In quick tests, that can cost roughly $0.30 to $1.00 per generation with a small model, depending on page size and output length.

Prism uses a cheaper patch-oriented flow:

1. The extension captures the live post-JavaScript DOM from the current page.
2. The backend builds an anchored DOM representation instead of sending raw HTML directly.
3. The backend assigns stable internal anchors and selector candidates to elements.
4. The skeletonizer keeps meaningful structure, text, attributes, nearby context, and layout hints while collapsing repetitive sibling runs and pruning deep subtrees.
5. Selected element metadata is sent alongside the compact skeleton, so exact user targets stay visible to the model.
6. The model is asked to emit small patch operations, CSS variable changes, and CSS rules instead of a full HTML rewrite.
7. The extension applies those patches to the live DOM and caches the result.

In other words, the LLM does not need to read every raw byte and then rewrite the entire page. It sees a compact, anchored, purpose-built view of the DOM and returns intent-level edits. That is the main reason the system can get good results with much less input and output.

In first-look testing, this brought many page generations below $0.01 while using a model like `gpt-5.4-nano`. The exact benchmark is not point-accurate yet; it was a quick initial measurement. A real benchmark with logged usage, output quality, and apples-to-apples model comparisons still needs to be built.

The bigger result is not only cost. The exciting part is that the compact representation lets a very small model do useful webpage edits. Everyone can switch the backend model through environment configuration, but for many current cases nano-level models are already doing the job.

There are still many changes that can improve both quality and cost. This area is actively being worked on.

## Current Limitation: Page-By-Page Editing

Right now Prism modifies one page at a time. That is useful for testing and for focused edits, but it is not enough for every real website workflow.

The next major product problem is full website coverage:

- editing consistent styles across multiple pages
- understanding shared layouts and components
- applying changes site-wide instead of only page-by-page
- keeping cost low while doing that

The next direction is to design a cheap method for whole-website modification without blindly sending every page's full HTML to the model.

## Setup Tutorial

### 1. Clone The Repo

```bash
git clone https://github.com/5en5e1/prism.git
cd prism
```

### 2. Create The Backend Environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and set:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_DEFAULT_MODEL=gpt-5.4-nano
```

You can use another model if you want. The backend owns the model choice.

### 3. Run The Backend

From the `backend` directory:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The extension expects the backend at:

```text
http://127.0.0.1:8000
```

### 4. Load The Chrome Extension

1. Open Chrome.
2. Go to `chrome://extensions`.
3. Enable Developer Mode.
4. Click `Load unpacked`.
5. Select the `prism-extension` folder.

### 5. Use Prism

1. Open a normal `http` or `https` webpage.
2. Click the Prism extension icon.
3. Write a prompt.
4. Optionally choose a template.
5. Optionally use `Pick` to select exact page elements.
6. Click `Generate`.

Generated saves appear in the popup. Cached webpages can be reviewed and cleared from the options page.

## Development Notes

Backend routes used by the extension:

- `/api/v1/health`
- `/api/v1/modes`
- `/api/v1/process`

Important extension files:

- `prism-extension/popup/popup.html`
- `prism-extension/popup/popup.css`
- `prism-extension/popup/popup.js`
- `prism-extension/src/content.js`
- `prism-extension/src/background.js`
- `prism-extension/options/options.html`

Important backend files:

- `backend/app/api/v1/routes.py`
- `backend/app/handlers/dom_manipulation.py`
- `backend/app/preprocessing/anchor_skeleton.py`
- `backend/app/preprocessing/id_anchoring.py`
- `backend/app/preprocessing/patch_applier.py`
- `backend/app/prompts/modes/`

## Next Todo

- Add usage metrics.
- Estimate cost per generation in the UI or logs.
- Log every generation result.
- Store model, token, prompt, patch, and quality metadata for each run.
- Create a real cost comparison benchmark.
- Compare raw-HTML prompting against Prism's anchored skeleton and patch flow.
- Benchmark multiple models, including nano-level models and larger models.
- Improve output quality while keeping generation cost low.
- Design full website coverage so Prism can modify a whole site, not only one page at a time.

## License

Prism is licensed under the MIT License. See [LICENSE](LICENSE).
