# Backend Architecture Plan

## Core Architectural Decision

All three use cases share the same pipeline shape: receive page + user intent → preprocess HTML → build a use-case-specific prompt → call OpenAI → validate and transform the model output → return a structured response. The differences live in *preprocessing strategy*, *prompt template*, and *output schema*. That's exactly the shape that maps to a Strategy + Registry pattern.

Each use case is a self-contained **Handler** that declares its own request schema, response schema, preprocessing function, prompt template, model parameters, and response parser. The pipeline orchestrator is dumb: it looks up a handler by name and walks it through the stages. Adding QA or redesign later means dropping in a new handler class and a new prompts directory. No core code changes.

## Folder Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, mounts routers, registers exception handlers
│   ├── config.py                  # pydantic-settings, env-driven
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routes.py          # /api/v1/process endpoint
│   │   │   └── deps.py            # DI: handler resolution, auth, rate limit
│   ├── core/
│   │   ├── pipeline.py            # Orchestrator (preprocess → prompt → AI → parse → postprocess)
│   │   ├── registry.py            # Handler registry with decorator-based registration
│   │   ├── exceptions.py          # Exception hierarchy
│   │   └── tracing.py             # trace_id propagation, structured logging hooks
│   ├── handlers/
│   │   ├── __init__.py            # Auto-imports all handler modules so registration fires
│   │   ├── base.py                # Handler Protocol/ABC
│   │   ├── dom_manipulation.py    # Working implementation
│   │   ├── qa.py                  # NotImplemented stub, registered
│   │   └── redesign.py            # NotImplemented stub, registered
│   ├── ai/
│   │   ├── client.py              # Async OpenAI wrapper
│   │   ├── retry.py               # Backoff policy, transient vs. fatal classification
│   │   └── token_counter.py       # tiktoken-based budgeting
│   ├── preprocessing/
│   │   ├── cleaner.py             # Strip scripts, comments, base64, hidden nodes
│   │   ├── skeletonizer.py        # Reduce HTML to structural skeleton + element IDs
│   │   ├── chunker.py             # Size-aware splitting strategies
│   │   └── id_anchoring.py        # Assign stable element IDs (path hashes)
│   ├── prompts/
│   │   ├── loader.py              # Reads manifest, caches Jinja templates at startup
│   │   ├── dom_manipulation/
│   │   │   ├── manifest.yaml
│   │   │   ├── v1/system.j2
│   │   │   ├── v1/user.j2
│   │   │   └── v1/examples.yaml   # Few-shot examples
│   │   ├── qa/
│   │   └── redesign/
│   ├── schemas/
│   │   ├── envelope.py            # Shared request/response envelope
│   │   ├── dom_manipulation.py    # Patch ops, per-handler request/response
│   │   ├── qa.py
│   │   └── redesign.py
│   └── utils/
│       ├── html.py                # lxml/bs4 helpers
│       └── logging.py
├── tests/
│   ├── fixtures/                  # Sample HTML pages
│   ├── unit/
│   └── integration/               # Real OpenAI calls behind a flag
├── pyproject.toml
├── .env.example
└── README.md
```

## Handler Interface

Define an abstract [`Handler`](backend/app/handlers/base.py) (Protocol or ABC) with this surface:

- `name: str` — registry key.
- `request_model: type[BaseModel]` — Pydantic schema for the handler-specific payload inside the request envelope.
- `response_model: type[BaseModel]` — Pydantic schema the AI output must conform to.
- `preprocess(html: str, params) -> ProcessedContext` — cleaning, skeletonization, chunking. Returns a context object containing the processed representation plus metadata (element-id map, original-size, chunk-count).
- `build_messages(context, params) -> list[Message]` — uses Jinja templates to construct the OpenAI chat messages. Owns the system prompt, few-shot examples, and the formatted user payload.
- `model_config: ModelConfig` — model name, temperature, max_tokens, response_format (`json_schema` for structured outputs is strongly preferred for DOM manipulation).
- `parse_response(raw: str, context) -> response_model` — validates the AI's JSON, raises a structured error if malformed.
- `postprocess(parsed, context) -> response_model` — runs sanity checks (do selectors exist? do inserted HTML fragments contain `<script>`?), strips disallowed content, resolves element-IDs back to CSS selectors.

Each handler registers via a decorator (`@register_handler("dom_manipulation")`) applied at class definition time. The [`handlers/__init__.py`](backend/app/handlers/__init__.py) imports every handler module so registration happens on app startup.

## Registration & Routing

A single endpoint, `POST /api/v1/process`, accepts a discriminated-union request body where `use_case` is the discriminator. Pydantic routes the inner `params` to the right per-handler schema automatically. The route handler:

1. Resolves the handler from the registry by `use_case`.
2. Hands the request + handler to the pipeline orchestrator.
3. Returns the pipeline result wrapped in the response envelope.

Single-endpoint with a discriminator is preferable to three endpoints because middleware (auth, rate limiting, tracing, error mapping) lives in one place, and the extension makes one call regardless of mode. If you later need streaming for redesign, add `POST /api/v1/process/stream` as a sibling rather than per-use-case endpoints.

## Request/Response Schemas

**Request envelope:**

```json
{
  "use_case": "dom_manipulation" | "qa" | "redesign",
  "page_url": "https://...",
  "html": "<full or skeleton HTML>",
  "user_prompt": "move the comments to the top",
  "params": { ... use-case-specific options ... },
  "client_metadata": { "extension_version": "...", "trace_id": "optional" }
}
```

**Response envelope:**

```json
{
  "trace_id": "uuid",
  "use_case": "dom_manipulation",
  "status": "ok" | "partial" | "error",
  "result": { ... use-case-specific payload ... },
  "warnings": [ ... ],
  "usage": { "input_tokens": N, "output_tokens": N, "model": "..." },
  "timing_ms": { "preprocess": N, "ai": N, "postprocess": N }
}
```

**For DOM manipulation specifically:** *do not* return modified HTML. Return a list of patch operations. This keeps payloads tiny, makes the AI's output easy to validate, lets the frontend apply changes without diffing, and avoids the model rewriting unrelated parts of the page. Operations:

- `move` — `{selector, target_selector, position}` where position is `before | after | prepend | append`
- `insert` — `{html, target_selector, position}`
- `replace` — `{selector, html}`
- `delete` — `{selector}`
- `set_attr` — `{selector, name, value}` (with `value: null` meaning remove)
- `add_class` / `remove_class` — `{selector, class_name}`
- `wrap` / `unwrap` — `{selector, wrapper_html?}`

Selectors are resolved from element-IDs the backend assigned during preprocessing. The AI works in ID-space; the response translates IDs to CSS selectors (or returns the IDs and lets the extension resolve them — your call, but resolving server-side keeps the extension simpler).

For QA later, the result will be `{answer, citations: [{element_id, selector, snippet}]}`. For redesign, it'll be `{css_rules, optional_html_patches}`. Different shapes, same envelope.

## HTML Preprocessing & Chunking

Page HTML in the wild is brutal: 500KB+ with inline base64 images, repeated ad markup, hydration noise. Sending raw HTML burns tokens and degrades model quality. The preprocessing pipeline:

**Stage 1 — Cleaning** (always runs):
- Strip `<script>`, `<style>` content (keep tags as markers if you need to preserve them visually).
- Remove HTML comments.
- Strip `data:` URI image sources, replace with `data-stripped="image"`.
- Remove `aria-*` noise beyond `aria-label`.
- Drop hidden elements (`display:none`, `hidden`, `aria-hidden="true"`) unless the task is QA where they might still be relevant.
- Collapse whitespace.

This typically cuts 50–80%.

**Stage 2 — Element-ID anchoring:**
Assign every meaningful element a stable short ID (e.g., `e0`, `e1`, ...) and record the ID → CSS-selector mapping in the context object. The AI sees `<div id-anchor="e42">` and refers to elements by `e42`. This is what makes the output safely round-trippable: the AI can't hallucinate a selector that doesn't exist, because IDs are a closed enumeration.

**Stage 3 — Skeletonization** (DOM manipulation, redesign):
For tasks that care about *structure*, not prose content, replace text nodes longer than ~80 chars with `[text:N chars]` placeholders. The model needs to know *where* the comments section is, not what every comment says.

For QA, do the opposite: preserve text, drop deep nested structural noise.

**Stage 4 — Size check & chunking** (only if still over budget):
Compute the token count (tiktoken). If under the model's input budget minus prompt overhead, send as-is. If over:

- **DOM manipulation**: chunk by top-level sections of `<body>`. Send a first pass with just the document skeleton (depth ≤ 3) + the user prompt, ask the model which section IDs are relevant, then send a second pass with those sections expanded. Two-pass is fine — DOM tasks are not latency-critical.
- **QA**: same two-pass pattern (relevance retrieval, then expansion).
- **Redesign**: usually a skeleton-only pass is enough; the model returns CSS, not transformed HTML.

Encode chunking strategy as a per-handler choice on the [`preprocess`](backend/app/handlers/base.py) method, not as a global feature. Different use cases want different chunking.

## Prompt Management

Each handler owns a directory under [`prompts/<handler_name>/`](backend/app/prompts/) with a `manifest.yaml`:

```yaml
name: dom_manipulation
active_version: v1
versions:
  v1:
    system: v1/system.j2
    user: v1/user.j2
    examples: v1/examples.yaml
    model: gpt-4o
    temperature: 0.2
    response_format: json_schema
    schema_ref: schemas.dom_manipulation.PatchList
```

At app startup, [`prompts/loader.py`](backend/app/prompts/loader.py) reads every manifest, validates references, and caches compiled Jinja templates and few-shot examples in memory. Handlers fetch templates by name from the loader; they never read files at request time.

Version handling: keep old versions in the tree (`v1/`, `v2/`) and switch the `active_version` field. This lets you A/B versions by handler-level config, roll back instantly, and replay old requests against new prompts in evals. Don't put prompts in code as f-strings — they need their own surface area for iteration.

For DOM manipulation, the system prompt should specify: the patch-op schema, the rule that the AI must only reference element-IDs from the provided HTML, the rule that inserted HTML must be inert (no `<script>`, no `on*=` attributes), and 2–3 few-shot examples showing realistic patch outputs.

Use OpenAI's structured outputs (`response_format: json_schema`) wherever the response schema is fixed — which is all three use cases. It eliminates 90% of the JSON-parsing failure modes.

## Config

Pydantic-settings with environment variables, `.env` for dev:

- `OPENAI_API_KEY`
- `OPENAI_DEFAULT_MODEL`, `OPENAI_TIMEOUT_S`
- `MAX_INPUT_HTML_BYTES` (hard limit before preprocessing — reject above ~5MB)
- `MAX_TOKENS_PER_REQUEST`
- `CACHE_BACKEND` (`memory | redis | none`), `REDIS_URL`
- `CORS_ALLOWED_ORIGINS` (the extension origin)
- `LOG_LEVEL`, `LOG_FORMAT` (json in prod)
- `RATE_LIMIT_PER_MINUTE_PER_IP`
- `FEATURE_FLAGS` map (per-handler enable/disable, useful for shipping with QA/redesign disabled)

## Error Handling

Exception hierarchy rooted at `PipelineError`:

- `PreprocessingError` (subclasses: `HTMLParseError`, `OversizeError`)
- `AIError` (subclasses: `RateLimitError`, `TimeoutError`, `ContentFilterError`, `MalformedResponseError`)
- `HandlerError` (subclasses: `HandlerNotFoundError`, `ValidationError`, `PostprocessError`)

A single FastAPI exception handler maps each to a structured error response:

```json
{
  "trace_id": "...",
  "status": "error",
  "error": {
    "code": "AI_RATE_LIMIT",
    "message": "...",
    "retryable": true,
    "stage": "ai_call"
  }
}
```

Retry policy lives in [`ai/retry.py`](backend/app/ai/retry.py). Retry on `RateLimitError`, `TimeoutError`, transient network errors with exponential backoff + jitter, capped at ~3 attempts. Do not retry `ContentFilterError`, `ValidationError`, or `MalformedResponseError` blindly — but for `MalformedResponseError`, allow exactly one self-repair attempt: resend with the parse error appended to the prompt asking the model to fix its JSON. If that fails, surface the error.

Every request gets a `trace_id` generated at the API edge, threaded through logs, included in every response and error.

## Other Decisions Worth Flagging

**Output safety on DOM manipulation.** Any `insert`/`replace` op carrying HTML must be sanitized server-side before returning: no `<script>`, no `on*` event-handler attributes, no `javascript:` URLs, no `<iframe>` to untrusted origins. The extension applies whatever you return verbatim — assume your server is the last line of defense, not the extension.

**Caching.** Key = hash(`use_case` + `model` + `prompt_version` + `user_prompt` + `html_skeleton_hash`). For identical repeated queries the AI call is skipped entirely. Start with in-memory LRU, move to Redis when you need it. This matters more than you'd think; users iterate on prompts against the same page.

**Async everywhere.** FastAPI async routes, OpenAI's async client, async preprocessing where chunking is parallelizable. A single redesign request might fan out to N parallel chunk calls.

**Token budgeting before AI call.** Count tokens after preprocessing. If still over budget, prefer truncation strategies declared by the handler (e.g., DOM handler truncates by dropping subtrees of low-relevance siblings) over silent failure. Return a `warnings` array entry when truncation happened.

**API versioning.** Mount everything under `/api/v1/`. The extension ships independently and will lag.

**Don't build the extension auth story yet, but reserve the seam.** Add a [`deps.py`](backend/app/api/v1/deps.py) slot for `get_current_user` that returns an anonymous principal today. When you add auth (API keys per install, OAuth, whatever), it's a swap rather than a refactor.

**Observability.** Log every stage with structured fields: trace_id, use_case, model, input_tokens, output_tokens, latency_ms, status. Even at low volume this pays for itself when debugging a bad prompt version.

**Evaluation harness, eventually.** Once you have two or more handlers, you'll want a `tests/eval/` directory: a set of fixture pages + prompts + expected behaviors, runnable against any prompt version. Doesn't need to exist on day one, but the manifest-versioned prompt structure is what makes it possible later.

---

## Implementation Order

The order to build this in:

1. **Schemas + envelope first** — Define the request/response envelope and base schemas
2. **Handler ABC + registry** — Create the handler interface and registration system
3. **Echo handler** — Build a no-op echo handler to validate the wiring end-to-end
4. **Preprocessing** — Implement cleaner + skeletonizer + ID anchoring
5. **DOM manipulation handler** — Build the first real handler with prompts
6. **Caching and retry** — Add resilience and performance optimizations
7. **QA and redesign handlers** — Each should be a 1–2 day drop-in after the foundation

QA and redesign should each be a 1–2 day drop-in after the foundation is built, not a re-architecture.