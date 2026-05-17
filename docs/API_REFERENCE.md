# API Reference

Complete technical reference for the HTML Manipulation Backend API.

## Table of Contents

- [Introduction](#introduction)
- [Common Concepts](#common-concepts)
- [Endpoints](#endpoints)
- [Use Cases](#use-cases)
- [Request Schemas](#request-schemas)
- [Response Schemas](#response-schemas)
- [Error Handling](#error-handling)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Changelog](#changelog)

---

## Introduction

### API Overview

The HTML Manipulation API is an AI-powered backend service that processes HTML content and applies intelligent modifications based on natural language instructions. The API uses advanced language models to understand user intent and generate precise DOM manipulation operations.

**Key Features:**
- Natural language HTML manipulation
- Patch-based editing (preserves live DOM state)
- CSS theming and styling
- Mode-based transformations
- Trace ID support for request tracking
- Detailed usage metrics and timing breakdowns

### Base URL

```
http://localhost:8000
```

For production deployments, replace with your actual domain.

### Authentication

**Current:** No authentication required.

**Future:** Token-based authentication is planned for production deployments. When implemented, requests will require an `Authorization` header:

```
Authorization: Bearer <your-api-token>
```

### Rate Limiting

**Default:** 60 requests per minute per IP address.

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets (Unix timestamp)

When rate limited, the API returns HTTP 429 with:
```json
{
  "detail": "Rate limit exceeded. Try again in X seconds."
}
```

### API Versioning

The API uses URL-based versioning: `/api/v1/...`

Current version: **v1.0**

Breaking changes will result in a new version (v2, v3, etc.). Non-breaking changes and additions are made to existing versions.

---

## Common Concepts

### Request/Response Envelope

All API requests and responses use a consistent envelope structure that wraps the actual payload with metadata.

**Request Envelope Fields:**
- `page_url`: URL of the page being processed
- `html`: HTML content to process
- `user_prompt`: Natural language instruction
- `selected_mode`: Optional mode key for predefined transformations
- `params`: Handler-specific parameters
- `client_metadata`: Client information and trace ID

**Response Envelope Fields:**
- `trace_id`: Unique identifier for request tracking
- `use_case`: Use case that was executed
- `status`: Response status (`ok`, `partial`, `error`)
- `result`: Use-case-specific result payload
- `warnings`: Non-fatal warnings
- `usage`: Token usage information
- `timing_ms`: Timing breakdown
- `error`: Error details (if status is `error`)

### Error Handling

Errors follow a consistent structure with actionable information:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable description",
  "retryable": true,
  "stage": "pipeline_stage"
}
```

**Error Codes:**
- `OVERSIZE_ERROR`: HTML exceeds size limit
- `EMPTY_PROMPT`: No instruction provided
- `VALIDATION_ERROR`: Invalid request parameters
- `AI_ERROR`: AI service error
- `INTERNAL_ERROR`: Unexpected server error

### Trace IDs

Trace IDs enable request tracking across the system:

1. **Client-provided:** Include `trace_id` in `client_metadata`
2. **Server-generated:** If not provided, server generates a UUID
3. **Response:** Always included in response for correlation

Use trace IDs for:
- Debugging failed requests
- Correlating logs across services
- Performance analysis

### Status Values

Response `status` indicates the outcome:

- **`ok`**: Request completed successfully
- **`partial`**: Request completed with warnings (some operations may have failed)
- **`error`**: Request failed (see `error` field for details)

### Usage Metrics

Token usage is tracked for cost monitoring and optimization:

```json
{
  "input_tokens": 15234,
  "output_tokens": 892,
  "model": "gpt-4o-2024-08-06"
}
```

**Token Budgets:**
- DOM skeleton: 60,000 tokens (configurable)
- Patch response: 8,000 tokens (configurable)
- Full HTML generation: 32,000 tokens (configurable)

---

## Endpoints

### Health Check

Check API availability and version.

**Endpoint:** `GET /api/v1/health`

**Request:** None

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

**Status Codes:**
- `200 OK`: Service is healthy
- `503 Service Unavailable`: Service is down

**Example:**
```bash
curl http://localhost:8000/api/v1/health
```

---

### Get Modes

Retrieve available transformation modes.

**Endpoint:** `GET /api/v1/modes`

**Request:** None

**Response:**
```json
{
  "modes": [
    {
      "key": "modern",
      "label": "Modern Design"
    },
    {
      "key": "futuristic",
      "label": "Futuristic Theme"
    },
    {
      "key": "cartoon",
      "label": "Cartoon Style"
    },
    {
      "key": "solarpunk",
      "label": "Solarpunk Aesthetic"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Modes retrieved successfully

**Example:**
```bash
curl http://localhost:8000/api/v1/modes
```

---

### Process Request

Main processing endpoint for HTML manipulation.

**Endpoint:** `POST /api/v1/process`

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "page_url": "https://example.com",
  "html": "<html>...</html>",
  "user_prompt": "Make the header blue and increase font size",
  "selected_mode": null,
  "params": {},
  "client_metadata": {
    "extension_version": "1.0.0",
    "trace_id": "optional-trace-id"
  }
}
```

**Response:**

```json
{
  "trace_id": "abc123-def456-ghi789",
  "use_case": "dom_manipulation",
  "status": "ok",
  "result": {
    "patches": [...],
    "css_vars": {},
    "css_rules": [],
    "skipped": [],
    "modified_html": "<html>...</html>",
    "changes_summary": "Modified header color and font size",
    "original_size": 45678,
    "modified_size": 45892
  },
  "warnings": [],
  "usage": {
    "input_tokens": 15234,
    "output_tokens": 892,
    "model": "gpt-4o-2024-08-06"
  },
  "timing_ms": {
    "preprocess_ms": 234.5,
    "ai_ms": 1567.8,
    "postprocess_ms": 123.4,
    "total_ms": 1925.7
  },
  "error": null
}
```

**Status Codes:**
- `200 OK`: Request processed (check `status` field for outcome)
- `422 Unprocessable Entity`: Invalid request body
- `429 Too Many Requests`: Rate limit exceeded

---

## Use Cases

### DOM Manipulation

The primary use case for HTML modification through patch-based operations.

#### Request Parameters

**Required:**
- `page_url` (string): URL of the page being processed
- `html` (string): HTML content to process
- `user_prompt` (string): Natural language instruction (required if no mode selected)

**Optional:**
- `selected_mode` (string|null): Mode key for predefined transformations
- `params` (object): Handler-specific parameters
  - `preserve_formatting` (boolean, default: `true`): Preserve original HTML formatting
  - `validate_selectors` (boolean, default: `true`): Validate selectors before applying

**Client Metadata:**
- `extension_version` (string|null): Client version
- `trace_id` (string|null): Client-provided trace ID

#### Response Structure

**Result Object:**

```json
{
  "patches": [
    {
      "op": "set_style",
      "selector": "header",
      "style": "background-color: blue;",
      "fallback_selector": "body > header:first-of-type",
      "anchor_id": "42"
    }
  ],
  "css_vars": {
    "--primary-color": "#007bff",
    "--header-bg": "#1a1a1a"
  },
  "css_rules": [
    "header { font-size: 1.5rem !important; }"
  ],
  "skipped": [],
  "modified_html": "<html>...</html>",
  "changes_summary": "Modified header styling",
  "original_size": 45678,
  "modified_size": 45892
}
```

**Field Descriptions:**

- **`patches`** (array): Ordered list of DOM operations to apply
  - Each patch includes operation type, selectors, and data
  - Applied sequentially to the live DOM
  - Preserves JavaScript state and event listeners

- **`css_vars`** (object): CSS custom properties to set site-wide
  - Applied to `:root` with high specificity
  - Non-destructive theming approach
  - Overrides author styles

- **`css_rules`** (array): Site-wide CSS rules to inject
  - Selector-based changes that apply to all matching elements
  - Immune to DOM virtualization and SPA re-renders
  - Preferred for category-wide changes

- **`skipped`** (array): Patches that couldn't be resolved
  - Contains descriptions of failed operations
  - Useful for debugging and partial success scenarios

- **`modified_html`** (string): Server-applied HTML fallback
  - Only included if `DOM_EMIT_SERVER_HTML=true`
  - Lossy on complex pages with JavaScript
  - For non-JS consumers only

- **`changes_summary`** (string): Brief description of changes made

- **`original_size`** (integer): Original HTML size in bytes

- **`modified_size`** (integer): Modified HTML size in bytes

#### Patch Operations

**Available Operations:**

1. **`set_text`**: Replace element's text content
   ```json
   {
     "op": "set_text",
     "target": "42",
     "selector": "h1",
     "text": "New Title"
   }
   ```

2. **`set_attr`**: Set or remove an attribute
   ```json
   {
     "op": "set_attr",
     "target": "42",
     "selector": "img",
     "name": "alt",
     "value": "Description"
   }
   ```

3. **`set_style`**: Replace inline style attribute
   ```json
   {
     "op": "set_style",
     "target": "42",
     "selector": "div",
     "style": "color: red; font-size: 16px;"
   }
   ```

4. **`set_css_var`**: Set CSS custom property site-wide
   ```json
   {
     "op": "set_css_var",
     "name": "--primary-color",
     "value": "#007bff"
   }
   ```

5. **`add_css_rule`**: Inject site-wide CSS rule
   ```json
   {
     "op": "add_css_rule",
     "css": ".button { border-radius: 8px !important; }"
   }
   ```

6. **`add_class`**: Add CSS class to element
   ```json
   {
     "op": "add_class",
     "target": "42",
     "selector": "div",
     "class_name": "highlight"
   }
   ```

7. **`remove_class`**: Remove CSS class from element
   ```json
   {
     "op": "remove_class",
     "target": "42",
     "selector": "div",
     "class_name": "old-style"
   }
   ```

8. **`replace_inner`**: Replace element's inner HTML
   ```json
   {
     "op": "replace_inner",
     "target": "42",
     "selector": "div",
     "html": "<p>New content</p>"
   }
   ```

9. **`replace_element`**: Replace entire element
   ```json
   {
     "op": "replace_element",
     "target": "42",
     "selector": "div",
     "html": "<section>Replacement</section>"
   }
   ```

10. **`insert`**: Insert HTML relative to element
    ```json
    {
      "op": "insert",
      "target": "42",
      "selector": "div",
      "html": "<p>Inserted content</p>",
      "position": "after"
    }
    ```

11. **`delete`**: Delete an element
    ```json
    {
      "op": "delete",
      "target": "42",
      "selector": "div"
    }
    ```

12. **`move`**: Move element to new location
    ```json
    {
      "op": "move",
      "target": "42",
      "selector": "div",
      "to": "84",
      "to_selector": "section",
      "position": "append"
    }
    ```

#### Common Use Cases

**1. Theming/Color Changes:**
```json
{
  "user_prompt": "Make the site dark mode with blue accents",
  "selected_mode": null
}
```
Result: CSS variables and rules for site-wide theming

**2. Layout Modifications:**
```json
{
  "user_prompt": "Move the sidebar to the right side",
  "selected_mode": null
}
```
Result: Move operations and CSS rules

**3. Content Updates:**
```json
{
  "user_prompt": "Change all headings to be more friendly",
  "selected_mode": null
}
```
Result: Text replacement operations

**4. Mode-Based Transformations:**
```json
{
  "user_prompt": "",
  "selected_mode": "modern"
}
```
Result: Predefined modern design transformations

**5. Combined Mode + Custom:**
```json
{
  "user_prompt": "Also make the buttons larger",
  "selected_mode": "futuristic"
}
```
Result: Futuristic mode + custom button modifications

#### Full Request/Response Example

**Request:**
```json
{
  "page_url": "https://example.com",
  "html": "<!DOCTYPE html><html><head><title>Example</title></head><body><header><h1>Welcome</h1></header><main><p>Content here</p></main></body></html>",
  "user_prompt": "Make the header background blue and the title white",
  "selected_mode": null,
  "params": {
    "preserve_formatting": true,
    "validate_selectors": true
  },
  "client_metadata": {
    "extension_version": "1.0.0",
    "trace_id": "req-12345"
  }
}
```

**Response:**
```json
{
  "trace_id": "req-12345",
  "use_case": "dom_manipulation",
  "status": "ok",
  "result": {
    "patches": [
      {
        "op": "set_style",
        "target": "1",
        "selector": "header",
        "style": "background-color: blue;",
        "fallback_selector": "body > header"
      },
      {
        "op": "set_style",
        "target": "2",
        "selector": "h1",
        "style": "color: white;",
        "fallback_selector": "header > h1"
      }
    ],
    "css_vars": {},
    "css_rules": [],
    "skipped": [],
    "modified_html": "<!DOCTYPE html><html><head><title>Example</title></head><body><header style=\"background-color: blue;\"><h1 style=\"color: white;\">Welcome</h1></header><main><p>Content here</p></main></body></html>",
    "changes_summary": "Modified header background to blue and title color to white",
    "original_size": 156,
    "modified_size": 198
  },
  "warnings": [],
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 156,
    "model": "gpt-4o-2024-08-06"
  },
  "timing_ms": {
    "preprocess_ms": 45.2,
    "ai_ms": 892.3,
    "postprocess_ms": 23.1,
    "total_ms": 960.6
  },
  "error": null
}
```

---

### QA (Planned)

Question-answering use case for HTML content analysis.

**Status:** Planned for future release

**Planned Features:**
- Extract information from HTML
- Answer questions about page content
- Summarize page sections
- Identify specific elements

---

### Redesign (Planned)

Complete page redesign use case.

**Status:** Planned for future release

**Planned Features:**
- Full page layout redesign
- Component-based transformations
- Design system application
- Accessibility improvements

---

## Request Schemas

### ProcessRequest

Complete request envelope schema.

```typescript
{
  page_url: string;              // Required: URL of the page
  html: string;                  // Required: HTML content (max 10MB)
  user_prompt: string;           // Required if no mode selected
  selected_mode: string | null;  // Optional: Mode key or null
  params: {                      // Optional: Handler parameters
    preserve_formatting?: boolean;  // Default: true
    validate_selectors?: boolean;   // Default: true
  };
  client_metadata: {             // Optional: Client info
    extension_version?: string;
    trace_id?: string;
  };
}
```

**Constraints:**
- `html`: Maximum 10,485,760 bytes (10MB)
- `user_prompt`: Required when `selected_mode` is null
- `selected_mode`: Must be a valid mode key from `/api/v1/modes` or null
- `page_url`: Must be a valid URL string

**Validation Rules:**
1. Either `selected_mode` or `user_prompt` must be provided
2. If mode is selected but has no instruction, `user_prompt` is required
3. HTML size must not exceed configured limit
4. Mode key must exist in backend configuration

---

## Response Schemas

### ProcessResponse

Complete response envelope schema.

```typescript
{
  trace_id: string;              // Request trace ID
  use_case: string;              // "dom_manipulation"
  status: "ok" | "partial" | "error";
  result: {                      // Use-case-specific result
    patches: Array<PatchOperation>;
    css_vars: Record<string, string>;
    css_rules: Array<string>;
    skipped: Array<string>;
    modified_html: string;
    changes_summary: string;
    original_size: number;
    modified_size: number;
  } | null;
  warnings: Array<string>;       // Non-fatal warnings
  usage: {                       // Token usage (if available)
    input_tokens: number;
    output_tokens: number;
    model: string;
  } | null;
  timing_ms: {                   // Timing breakdown (if available)
    preprocess_ms: number;
    ai_ms: number;
    postprocess_ms: number;
    total_ms: number;
  } | null;
  error: {                       // Error details (if status is error)
    code: string;
    message: string;
    retryable: boolean;
    stage: string;
  } | null;
}
```

### UsageInfo

Token usage information.

```typescript
{
  input_tokens: number;    // Input tokens consumed
  output_tokens: number;   // Output tokens generated
  model: string;           // Model identifier
}
```

### TimingInfo

Request timing breakdown.

```typescript
{
  preprocess_ms: number;   // Preprocessing time
  ai_ms: number;           // AI call time
  postprocess_ms: number;  // Postprocessing time
  total_ms: number;        // Total request time
}
```

### ErrorDetail

Error information structure.

```typescript
{
  code: string;        // Error code (e.g., "OVERSIZE_ERROR")
  message: string;     // Human-readable message
  retryable: boolean;  // Whether retry may succeed
  stage: string;       // Pipeline stage where error occurred
}
```

---

## Error Handling

### Error Response Format

All errors return HTTP 200 with `status: "error"` in the response body:

```json
{
  "trace_id": "abc-123",
  "use_case": "dom_manipulation",
  "status": "error",
  "result": null,
  "warnings": [],
  "usage": null,
  "timing_ms": null,
  "error": {
    "code": "OVERSIZE_ERROR",
    "message": "HTML size 12000000 bytes exceeds limit of 10485760 bytes",
    "retryable": false,
    "stage": "validation"
  }
}
```

### Error Codes

| Code | Description | Retryable | Stage |
|------|-------------|-----------|-------|
| `OVERSIZE_ERROR` | HTML exceeds size limit | No | validation |
| `EMPTY_PROMPT` | No instruction provided | No | validation |
| `VALIDATION_ERROR` | Invalid request parameters | No | validation |
| `AI_ERROR` | AI service error | Yes | ai_call |
| `TIMEOUT_ERROR` | Request timeout | Yes | ai_call |
| `RATE_LIMIT_ERROR` | AI rate limit hit | Yes | ai_call |
| `INTERNAL_ERROR` | Unexpected server error | Maybe | unknown |

### Retryable vs Non-Retryable Errors

**Retryable Errors** (`retryable: true`):
- Temporary AI service issues
- Rate limiting
- Timeout errors
- Network issues

**Retry Strategy:**
- Wait 1-5 seconds before retry
- Use exponential backoff
- Maximum 3 retry attempts

**Non-Retryable Errors** (`retryable: false`):
- Invalid request format
- HTML size exceeded
- Missing required fields
- Invalid mode selection

**Action:** Fix the request and resubmit.

### Example Error Responses

**Oversize Error:**
```json
{
  "trace_id": "trace-123",
  "use_case": "dom_manipulation",
  "status": "error",
  "result": null,
  "warnings": [],
  "usage": null,
  "timing_ms": null,
  "error": {
    "code": "OVERSIZE_ERROR",
    "message": "HTML size 12000000 bytes exceeds limit of 10485760 bytes",
    "retryable": false,
    "stage": "validation"
  }
}
```

**Empty Prompt Error:**
```json
{
  "trace_id": "trace-456",
  "use_case": "dom_manipulation",
  "status": "error",
  "result": null,
  "warnings": [],
  "usage": null,
  "timing_ms": null,
  "error": {
    "code": "EMPTY_PROMPT",
    "message": "Selected mode 'modern' has no instruction configured and no user prompt was provided.",
    "retryable": false,
    "stage": "validation"
  }
}
```

**AI Service Error:**
```json
{
  "trace_id": "trace-789",
  "use_case": "dom_manipulation",
  "status": "error",
  "result": null,
  "warnings": [],
  "usage": null,
  "timing_ms": {
    "preprocess_ms": 123.4,
    "ai_ms": 0,
    "postprocess_ms": 0,
    "total_ms": 123.4
  },
  "error": {
    "code": "AI_ERROR",
    "message": "OpenAI API error: Rate limit exceeded",
    "retryable": true,
    "stage": "ai_call"
  }
}
```

---

## Examples

### cURL Examples

**Basic Request:**
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "page_url": "https://example.com",
    "html": "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>",
    "user_prompt": "Make the heading blue",
    "selected_mode": null,
    "params": {},
    "client_metadata": {
      "extension_version": "1.0.0"
    }
  }'
```

**With Mode:**
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "page_url": "https://example.com",
    "html": "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>",
    "user_prompt": "",
    "selected_mode": "modern",
    "params": {},
    "client_metadata": {}
  }'
```

**With Trace ID:**
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "page_url": "https://example.com",
    "html": "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>",
    "user_prompt": "Make it dark mode",
    "selected_mode": null,
    "params": {},
    "client_metadata": {
      "trace_id": "my-trace-123"
    }
  }'
```

### Python Examples

**Using requests library:**

```python
import requests
import json

# Basic request
url = "http://localhost:8000/api/v1/process"
payload = {
    "page_url": "https://example.com",
    "html": "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>",
    "user_prompt": "Make the heading blue",
    "selected_mode": None,
    "params": {},
    "client_metadata": {
        "extension_version": "1.0.0"
    }
}

response = requests.post(url, json=payload)
result = response.json()

if result["status"] == "ok":
    print(f"Success! Applied {len(result['result']['patches'])} patches")
    print(f"Changes: {result['result']['changes_summary']}")
elif result["status"] == "error":
    print(f"Error: {result['error']['message']}")
```

**With error handling:**

```python
import requests
import time

def process_html(html, prompt, max_retries=3):
    url = "http://localhost:8000/api/v1/process"
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json={
                    "page_url": "https://example.com",
                    "html": html,
                    "user_prompt": prompt,
                    "selected_mode": None,
                    "params": {},
                    "client_metadata": {}
                },
                timeout=30
            )
            
            result = response.json()
            
            if result["status"] == "ok":
                return result
            elif result["status"] == "error":
                error = result["error"]
                if error["retryable"] and attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Retryable error, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"API error: {error['message']}")
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"Timeout, retrying...")
                continue
            raise
    
    raise Exception("Max retries exceeded")

# Usage
try:
    result = process_html(
        html="<html><body><h1>Test</h1></body></html>",
        prompt="Make it colorful"
    )
    print(f"Success: {result['result']['changes_summary']}")
except Exception as e:
    print(f"Failed: {e}")
```

### JavaScript/Fetch Examples

**Basic request:**

```javascript
async function processHTML(html, prompt) {
  const response = await fetch('http://localhost:8000/api/v1/process', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      page_url: 'https://example.com',
      html: html,
      user_prompt: prompt,
      selected_mode: null,
      params: {},
      client_metadata: {
        extension_version: '1.0.0'
      }
    })
  });

  const result = await response.json();
  
  if (result.status === 'ok') {
    console.log('Success!', result.result.changes_summary);
    return result.result;
  } else if (result.status === 'error') {
    throw new Error(result.error.message);
  }
}

// Usage
processHTML(
  '<!DOCTYPE html><html><body><h1>Hello</h1></body></html>',
  'Make the heading blue'
).then(result => {
  console.log('Patches:', result.patches);
}).catch(error => {
  console.error('Error:', error);
});
```

**With retry logic:**

```javascript
async function processHTMLWithRetry(html, prompt, maxRetries = 3) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await fetch('http://localhost:8000/api/v1/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          page_url: window.location.href,
          html: html,
          user_prompt: prompt,
          selected_mode: null,
          params: {},
          client_metadata: {
            extension_version: '1.0.0',
            trace_id: `trace-${Date.now()}`
          }
        })
      });

      const result = await response.json();
      
      if (result.status === 'ok') {
        return result.result;
      } else if (result.status === 'error') {
        const error = result.error;
        
        if (error.retryable && attempt < maxRetries - 1) {
          const waitTime = Math.pow(2, attempt) * 1000;
          console.log(`Retryable error, waiting ${waitTime}ms...`);
          await new Promise(resolve => setTimeout(resolve, waitTime));
          continue;
        } else {
          throw new Error(error.message);
        }
      }
    } catch (error) {
      if (attempt < maxRetries - 1) {
        console.log('Request failed, retrying...');
        continue;
      }
      throw error;
    }
  }
  
  throw new Error('Max retries exceeded');
}

// Usage
processHTMLWithRetry(
  document.documentElement.outerHTML,
  'Make it dark mode'
).then(result => {
  // Apply patches to DOM
  result.patches.forEach(patch => {
    // Apply patch logic here
  });
}).catch(error => {
  console.error('Failed to process:', error);
});
```

### Response Examples

**Successful Response:**
```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "use_case": "dom_manipulation",
  "status": "ok",
  "result": {
    "patches": [
      {
        "op": "set_css_var",
        "name": "--bg-color",
        "value": "#1a1a1a"
      },
      {
        "op": "set_css_var",
        "name": "--text-color",
        "value": "#ffffff"
      },
      {
        "op": "add_css_rule",
        "css": "body { background-color: var(--bg-color); color: var(--text-color); }"
      }
    ],
    "css_vars": {
      "--bg-color": "#1a1a1a",
      "--text-color": "#ffffff"
    },
    "css_rules": [
      "body { background-color: var(--bg-color); color: var(--text-color); }"
    ],
    "skipped": [],
    "modified_html": "<!DOCTYPE html><html>...</html>",
    "changes_summary": "Applied dark mode theme with dark background and light text",
    "original_size": 5432,
    "modified_size": 5678
  },
  "warnings": [],
  "usage": {
    "input_tokens": 2345,
    "output_tokens": 234,
    "model": "gpt-4o-2024-08-06"
  },
  "timing_ms": {
    "preprocess_ms": 123.4,
    "ai_ms": 1567.8,
    "postprocess_ms": 89.2,
    "total_ms": 1780.4
  },
  "error": null
}
```

**Partial Success Response:**
```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440001",
  "use_case": "dom_manipulation",
  "status": "partial",
  "result": {
    "patches": [
      {
        "op": "set_style",
        "target": "1",
        "selector": "header",
        "style": "background-color: blue;"
      }
    ],
    "css_vars": {},
    "css_rules": [],
    "skipped": [
      "Could not find element with selector '.non-existent-class'"
    ],
    "modified_html": "<!DOCTYPE html><html>...</html>",
    "changes_summary": "Modified header background (1 operation skipped)",
    "original_size": 3456,
    "modified_size": 3489
  },
  "warnings": [
    "Some selectors could not be resolved"
  ],
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 156,
    "model": "gpt-4o-2024-08-06"
  },
  "timing_ms": {
    "preprocess_ms": 98.7,
    "ai_ms": 1234.5,
    "postprocess_ms": 67.8,
    "total_ms": 1401.0
  },
  "error": null
}
```

---

## Best Practices

### HTML Size Limits

**Default Limit:** 10MB (10,485,760 bytes)

**Recommendations:**
- Pre-process HTML to remove unnecessary content
- Strip large inline scripts and styles
- Remove comments and whitespace for large documents
- Consider chunking very large pages

**Size Optimization:**
```python
from bs4 import BeautifulSoup

def optimize_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Remove large inline scripts (keep external references)
    for script in soup.find_all('script'):
        if script.string and len(script.string) > 10000:
            script.extract()
    
    return str(soup)
```

### Token Budgeting

**Token Limits:**
- DOM skeleton: 60,000 tokens (input)
- Patch response: 8,000 tokens (output)
- Full HTML: 32,000 tokens (output)

**Optimization Strategies:**

1. **Use Compact Mode** (default):
   - Tighter text/class/attribute limits
   - Aggressive sibling collapse
   - Reduces tokens without affecting correctness

2. **Specific Prompts:**
   - Be specific about what to change
   - Avoid "redesign everything" requests
   - Target specific sections or elements

3. **Mode Selection:**
   - Use predefined modes when possible
   - Modes have optimized prompts
   - Combine mode + specific tweaks

### Caching Strategies

**Client-Side Caching:**

```javascript
class APICache {
  constructor(ttl = 300000) { // 5 minutes
    this.cache = new Map();
    this.ttl = ttl;
  }
  
  key(html, prompt, mode) {
    return `${mode || 'none'}:${prompt}:${this.hashHTML(html)}`;
  }
  
  hashHTML(html) {
    // Simple hash for demo - use better hash in production
    return html.length + html.substring(0, 100);
  }
  
  get(html, prompt, mode) {
    const k = this.key(html, prompt, mode);
    const entry = this.cache.get(k);
    
    if (entry && Date.now() - entry.timestamp < this.ttl) {
      return entry.data;
    }
    
    return null;
  }
  
  set(html, prompt, mode, data) {
    const k = this.key(html, prompt, mode);
    this.cache.set(k, {
      data: data,
      timestamp: Date.now()
    });
  }
}

// Usage
const cache = new APICache();

async function processWithCache(html, prompt, mode) {
  const cached = cache.get(html, prompt, mode);
  if (cached) {
    console.log('Using cached result');
    return cached;
  }
  
  const result = await processHTML(html, prompt, mode);
  cache.set(html, prompt, mode, result);
  return result;
}
```

**Server-Side Caching:**
- Configured via `CACHE_BACKEND` environment variable
- Options: `memory`, `redis`, `none`
- Caches preprocessed HTML skeletons
- Reduces preprocessing time for repeated requests

### Error Handling Recommendations

**1. Always Check Status:**
```javascript
const result = await processHTML(html, prompt);

if (result.status === 'ok') {
  // Success
  applyPatches(result.result.patches);
} else if (result.status === 'partial') {
  // Partial success
  console.warn('Some operations failed:', result.warnings);
  applyPatches(result.result.patches);
} else if (result.status === 'error') {
  // Error
  handleError(result.error);
}
```

**2. Implement Retry Logic:**
```javascript
async function processWithRetry(html, prompt, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const result = await processHTML(html, prompt);
      
      if (result.status === 'error' && result.error.retryable) {
        if (i < maxRetries - 1) {
          await sleep(Math.pow(2, i) * 1000);
          continue;
        }
      }
      
      return result;
    } catch (error) {
      if (i < maxRetries - 1) {
        await sleep(Math.pow(2, i) * 1000);
        continue;
      }
      throw error;
    }
  }
}
```

**3. Log Trace IDs:**
```javascript
const traceId = `trace-${Date.now()}-${Math.random()}`;

const result = await processHTML(html, prompt, {
  trace_id: traceId
});

console.log(`Request ${traceId}: ${result.status}`);
```

**4. Handle Timeouts:**
```javascript
async function processWithTimeout(html, prompt, timeout = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      signal: controller.signal,
      body: JSON.stringify({...})
    });
    
    return await response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}
```

### Performance Tips

**1. Minimize HTML Size:**
- Remove unnecessary elements before sending
- Strip large inline resources
- Use external stylesheets/scripts

**2. Use Specific Prompts:**
- "Change header color to blue" vs "Redesign the page"
- Specific prompts = faster processing
- Fewer tokens = lower cost

**3. Batch Related Changes:**
- Combine related changes in one request
- "Make header blue and footer gray" vs two separate requests
- Reduces API calls and latency

**4. Monitor Usage:**
```javascript
function logUsage(result) {
  if (result.usage) {
    console.log(`Tokens: ${result.usage.input_tokens} in, ${result.usage.output_tokens} out`);
    console.log(`Model: ${result.usage.model}`);
  }
  
  if (result.timing_ms) {
    console.log(`Time: ${result.timing_ms.total_ms}ms total`);
    console.log(`  - Preprocess: ${result.timing_ms.preprocess_ms}ms`);
    console.log(`  - AI: ${result.timing_ms.ai_ms}ms`);
    console.log(`  - Postprocess: ${result.timing_ms.postprocess_ms}ms`);
  }
}
```

---

## Changelog

### v1.0 (Current)

**Release Date:** 2026-05-17

**Features:**
- Initial API release
- DOM manipulation use case
- Patch-based editing with anchor IDs
- CSS variable and rule injection
- Mode-based transformations
- Trace ID support
- Usage metrics and timing breakdowns
- Comprehensive error handling

**Endpoints:**
- `GET /api/v1/health` - Health check
- `GET /api/v1/modes` - List available modes
- `POST /api/v1/process` - Process HTML

**Patch Operations:**
- `set_text` - Replace text content
- `set_attr` - Set/remove attributes
- `set_style` - Set inline styles
- `set_css_var` - Set CSS variables
- `add_css_rule` - Inject CSS rules
- `add_class` / `remove_class` - Manage classes
- `replace_inner` / `replace_element` - Replace HTML
- `insert` - Insert HTML
- `delete` - Remove elements
- `move` - Reposition elements

**Configuration:**
- HTML size limit: 10MB
- DOM skeleton budget: 60,000 tokens
- Patch response budget: 8,000 tokens
- Rate limit: 60 requests/minute/IP

**Known Limitations:**
- No authentication (planned for v2)
- Single use case (DOM manipulation)
- No batch processing
- No WebSocket support

---

## Support

For issues, questions, or feature requests:

1. Check this documentation
2. Review error messages and trace IDs
3. Consult the [Getting Started Guide](GETTING_STARTED.md)
4. See [Working with Bob](WORKING_WITH_BOB.md) for development

---

*Made with Bob*