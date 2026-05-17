# Full HTML Editing Pipeline

## Overview

The DOM manipulation handler has been redesigned to support **full HTML editing mode**, where the LLM receives and returns complete HTML pages with maximum flexibility for comprehensive modifications.

## Key Changes from Previous Architecture

### Before (Patch-Based)
- LLM received skeletonized HTML with element IDs
- Returned list of patch operations (move, insert, replace, etc.)
- Limited context due to skeletonization
- Complex selector validation and ID mapping

### After (Full HTML)
- LLM receives complete HTML with minimal cleaning
- Returns entire modified HTML page
- Full context for better understanding
- Direct HTML-to-HTML transformation

## Architecture

```
Raw HTML
    ↓
Minimal Cleaning (comments + whitespace only)
    ↓
Send Complete HTML to OpenAI (single request)
    ↓
Receive Complete Modified HTML
    ↓
Validate Structure
    ↓
Return Modified HTML
```

## Implementation Details

### 1. Response Schema ([`schemas/dom_manipulation.py`](backend/app/schemas/dom_manipulation.py))

```python
class DOMManipulationResult(BaseModel):
    modified_html: str  # Complete modified HTML page
    changes_summary: str  # Brief description of changes
    original_size: int  # Original HTML size in bytes
    modified_size: int  # Modified HTML size in bytes
```

### 2. Preprocessing ([`handlers/dom_manipulation.py`](backend/app/handlers/dom_manipulation.py))

**Removed:**
- Element ID anchoring
- Skeletonization
- Heavy cleaning

**Kept:**
- Minimal cleaning via `minimal_clean_html()`:
  - Remove HTML comments
  - Collapse excessive whitespace
  - Preserve all scripts, styles, content, attributes

### 3. System Prompt ([`prompts/dom_manipulation/v1/system.j2`](backend/app/prompts/dom_manipulation/v1/system.j2))

The LLM is instructed to:
- Modify any HTML structure, elements, or content
- Add/modify inline styles, style tags, CSS classes
- Change layout, positioning, colors, fonts
- Return COMPLETE modified HTML (from `<!DOCTYPE>` to `</html>`)
- Provide brief summary of changes

### 4. Token Budget

**Configuration updates:**
- `max_input_html_bytes`: 5MB → 10MB
- `max_tokens_per_request`: 100K → 120K tokens

**Strategy:**
- No chunking - send complete HTML in single request
- Leverage GPT-4o's 128K context window
- Log warnings if approaching limits but still process
- Accept potential quality degradation on massive pages

### 5. Postprocessing ([`handlers/dom_manipulation.py`](backend/app/handlers/dom_manipulation.py))

**Validation:**
- Parse HTML with BeautifulSoup to ensure valid structure
- Check for presence of `<html>` and `<body>` tags
- Optional safety checks (disabled by default for maximum flexibility)

**Safety checks (optional):**
- Detect suspicious script injections
- Scan for malicious event handlers
- Can be enabled by uncommenting validation code

## API Response Format

### Request
```json
{
  "use_case": "dom_manipulation",
  "page_url": "https://example.com",
  "html": "<!DOCTYPE html><html>...</html>",
  "user_prompt": "Move the sidebar to the top-right corner",
  "params": {}
}
```

### Response
```json
{
  "trace_id": "uuid",
  "use_case": "dom_manipulation",
  "status": "ok",
  "result": {
    "modified_html": "<!DOCTYPE html><html>...</html>",
    "changes_summary": "Added fixed positioning to sidebar and moved it to top-right corner with semi-transparent background.",
    "original_size": 15420,
    "modified_size": 15680
  },
  "usage": {
    "input_tokens": 3842,
    "output_tokens": 4156,
    "model": "gpt-4o"
  },
  "timing_ms": {
    "preprocess_ms": 45,
    "ai_ms": 2340,
    "postprocess_ms": 12,
    "total_ms": 2397
  }
}
```

## Benefits

1. **Maximum Flexibility**: LLM can modify anything anywhere in the page
2. **Full Context**: Sees entire page structure, styles, and scripts
3. **Simpler Architecture**: No element ID mapping, no patch operations
4. **Better Styling**: Can freely add/modify inline styles, style tags, classes
5. **Layout Control**: Can restructure entire page layout
6. **Single API Call**: No multi-pass processing or chunking

## Trade-offs

1. **Larger Responses**: Full HTML vs small patch list (~10-50x larger)
2. **Higher Token Cost**: More input/output tokens per request
3. **Frontend Diff**: Client needs to compute diffs for visualization
4. **Validation Complexity**: Must validate entire HTML structure

## Usage Examples

### Example 1: Move Sidebar
**Request:** "Move the sidebar to the top-right corner"

**LLM Actions:**
- Adds `position: fixed; top: 20px; right: 20px; z-index: 1000;` to sidebar
- Adjusts width and adds semi-transparent background
- Returns complete modified HTML

### Example 2: Redesign Header
**Request:** "Make the header sticky and add a shadow"

**LLM Actions:**
- Adds `position: sticky; top: 0; z-index: 100;` to header
- Adds `box-shadow: 0 2px 4px rgba(0,0,0,0.1);`
- Returns complete modified HTML

### Example 3: Change Color Scheme
**Request:** "Change the color scheme to dark mode"

**LLM Actions:**
- Modifies/adds style tag with dark mode colors
- Updates inline styles on key elements
- Changes background, text, and accent colors
- Returns complete modified HTML

## Migration Notes

### For Frontend Integration

**Before (Patch-Based):**
```javascript
// Apply patches one by one
response.result.patches.forEach(patch => {
  applyPatch(patch);
});
```

**After (Full HTML):**
```javascript
// Replace entire document or compute diff
const modifiedHTML = response.result.modified_html;
document.documentElement.innerHTML = modifiedHTML;
// Or use a diff library to show changes
```

### Backward Compatibility

The old patch-based system has been completely replaced. If you need to support both:
1. Create a new handler `dom_manipulation_v2` with full HTML mode
2. Keep old handler as `dom_manipulation_v1` 
3. Use feature flags to switch between versions

## Testing

Test the pipeline with:
```bash
cd backend
python test_dom_feature.py
```

Or make a direct API call:
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "use_case": "dom_manipulation",
    "page_url": "https://example.com",
    "html": "<!DOCTYPE html><html><body><h1>Test</h1></body></html>",
    "user_prompt": "Make the heading blue"
  }'
```

## Performance Considerations

- **Token Usage**: Expect 2-10x more tokens per request
- **Latency**: Similar to patch-based (single API call)
- **Cost**: Higher due to increased token usage
- **Quality**: Better results due to full context

## Future Enhancements

1. **Diff Generation**: Add server-side HTML diff for frontend visualization
2. **Streaming**: Support streaming responses for large HTML modifications
3. **Caching**: Cache based on HTML hash + prompt for repeated requests
4. **Validation Levels**: Configurable safety/validation strictness
5. **Rollback**: Store original HTML for easy rollback