# Working with Bob: An AI-Assisted Development Journey

> A comprehensive chronicle of building the DOM Patch Assistant through human-AI collaboration

[![Built with Bob](https://img.shields.io/badge/Built%20with-Bob%20AI-blue?style=flat-square)](https://github.com/yourusername/dom-patch-assistant)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Project Genesis](#project-genesis)
3. [Architecture Design Phase](#architecture-design-phase)
4. [Implementation Journey](#implementation-journey)
5. [Key Problem-Solving Moments](#key-problem-solving-moments)
6. [Testing & Validation](#testing--validation)
7. [Documentation Creation](#documentation-creation)
8. [Lessons Learned](#lessons-learned)
9. [Code Examples](#code-examples)
10. [Future Collaboration](#future-collaboration)

---

## Introduction

### What This Document Is About

This document chronicles the development of **DOM Patch Assistant**, a Chrome extension that uses AI to manipulate web pages through natural language commands. Unlike typical project documentation, this is a meta-narrative about the collaboration between a human developer and **Bob**, an AI coding assistant.

### Why Document the Bob Collaboration?

AI-assisted development is rapidly becoming mainstream, but there's limited documentation on *how* to effectively collaborate with AI on complex software projects. This document serves multiple purposes:

- **Transparency**: Show exactly how AI contributed to this project
- **Learning Resource**: Help others understand effective AI collaboration patterns
- **Historical Record**: Capture the state of AI-assisted development in 2026
- **Methodology**: Document what works (and what doesn't) when building with AI

### Project Overview

**DOM Patch Assistant** transforms any webpage using natural language commands. The system:
- Accepts HTML + user prompt from a Chrome extension
- Preprocesses HTML into an optimized representation
- Uses OpenAI GPT-4o to generate DOM manipulation patches
- Returns validated patches for real-time application

The project demonstrates sophisticated architectural patterns, robust error handling, and production-ready code quality—all developed through human-AI collaboration.

---

## Project Genesis

### The Initial Problem Statement

**Human's Vision:**
> "I want to build a Chrome extension that lets users modify any webpage using natural language. Users should be able to say things like 'make all headings blue' or 'hide the sidebar' and see the changes applied instantly."

**The Challenge:**
- Web pages are massive (often 500KB+ of HTML)
- AI models have token limits
- DOM manipulation must be precise and safe
- Changes need to work on dynamic/SPA sites
- The system must be fast and cost-effective

### How Bob Helped Define the Scope

**Bob's Initial Analysis:**

When presented with the problem, Bob immediately identified the core architectural challenge:

> "This is fundamentally a pipeline problem: HTML → Preprocessing → AI → Validation → Application. The key insight is that all future use cases (DOM manipulation, QA, redesign) will share this same pipeline shape, but differ in preprocessing strategy, prompt template, and output schema."

**Key Scoping Decisions Bob Made:**

1. **Strategy + Registry Pattern**: Suggested using a handler-based architecture where each use case is a self-contained strategy
2. **Preprocessing First**: Emphasized that token optimization through smart preprocessing was critical
3. **Patch-Based Output**: Recommended returning patch operations instead of full HTML for efficiency
4. **Extensibility**: Designed the system to easily accommodate future handlers (QA, redesign)

### Early Architectural Discussions

**The "Aha!" Moment:**

```
Human: "Should I have separate endpoints for each use case?"

Bob: "No. Use a single /api/v1/process endpoint with a discriminated union 
request body where 'use_case' is the discriminator. This keeps middleware 
(auth, rate limiting, tracing) in one place, and the extension makes one 
call regardless of mode."
```

This single insight shaped the entire API design and made the system dramatically more maintainable.

---

## Architecture Design Phase

### Strategy + Registry Pattern Suggestion

**Bob's Architectural Proposal:**

Bob suggested defining an abstract `Handler` interface with these responsibilities:

```python
class Handler(ABC, Generic[RequestT, ResponseT]):
    @property
    @abstractmethod
    def name(self) -> str:
        """Handler name used for registry lookup."""
        pass
    
    @abstractmethod
    async def preprocess(self, html: str, params: RequestT) -> ProcessedContext:
        """Preprocess HTML for this use case."""
        pass
    
    @abstractmethod
    async def build_messages(
        self, context: ProcessedContext, params: RequestT, user_prompt: str
    ) -> list[Message]:
        """Build OpenAI chat messages."""
        pass
    
    @abstractmethod
    async def parse_response(self, raw_response: str, context: ProcessedContext) -> ResponseT:
        """Parse and validate AI response."""
        pass
    
    @abstractmethod
    async def postprocess(self, parsed: ResponseT, context: ProcessedContext) -> ResponseT:
        """Apply postprocessing and safety checks."""
        pass
```

**Why This Pattern?**

Bob explained: *"Each handler owns its complete pipeline. Adding QA or redesign later means dropping in a new handler class and a new prompts directory. No core code changes. The pipeline orchestrator is dumb—it just walks handlers through stages."*

This turned out to be prescient. The architecture has remained stable through multiple iterations.

### Handler Interface Design

**The Evolution:**

1. **Initial Design**: Bob proposed a simple handler with just `process()` method
2. **Refinement**: After discussing preprocessing needs, Bob split it into distinct stages
3. **Final Design**: Added `ProcessedContext` to pass metadata between stages

**Key Design Decisions:**

- **Generic Types**: `Handler[RequestT, ResponseT]` for type safety
- **Async Throughout**: All methods async for I/O efficiency
- **Context Object**: `ProcessedContext` carries metadata without polluting handler state
- **Immutability**: Handlers are stateless; all state flows through method parameters

### Preprocessing Pipeline Decisions

**The Token Budget Challenge:**

```
Human: "How do I handle pages that are 500KB of HTML?"

Bob: "You need a multi-stage preprocessing pipeline:
1. Cleaning - Strip scripts, comments, base64 images (50-80% reduction)
2. Element-ID anchoring - Assign stable IDs for selector generation
3. Skeletonization - Replace text with placeholders for structure-focused tasks
4. Chunking - Only if still over budget, use two-pass relevance retrieval"
```

**Bob's Preprocessing Strategy:**

Bob designed a modular preprocessing system where each stage is independent:

```python
# Stage 1: Cleaning
cleaned_html = clean_html(raw_html, preserve_hidden=False)

# Stage 2: Element-ID Anchoring
id_map = assign_element_ids(cleaned_html)

# Stage 3: Skeletonization (for DOM manipulation)
skeleton = skeletonize(cleaned_html, max_text_length=80)

# Stage 4: Token Check & Chunking (if needed)
if count_tokens(skeleton) > budget:
    chunks = chunk_by_sections(skeleton)
```

Each stage is in its own module under `preprocessing/`, making the system testable and maintainable.

### Prompt Management System

**Bob's Prompt Architecture:**

Bob insisted on treating prompts as first-class artifacts, not code strings:

```yaml
# prompts/dom_manipulation/manifest.yaml
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
```

**Why This Matters:**

> "Prompts need their own surface area for iteration. You'll A/B test versions, roll back bad prompts, and replay old requests against new prompts in evals. Don't put prompts in f-strings—you'll regret it."

This proved invaluable. We've iterated on prompts 10+ times without touching code.

### Key Architectural Decisions with Bob's Reasoning

| Decision | Bob's Reasoning |
|----------|-----------------|
| **Single endpoint with discriminator** | "Keeps middleware in one place, extension makes one call regardless of mode" |
| **Patch operations vs full HTML** | "Keeps payloads tiny, makes AI output easy to validate, avoids model rewriting unrelated parts" |
| **Element-ID anchoring** | "AI can't hallucinate selectors that don't exist—IDs are a closed enumeration" |
| **Structured outputs (json_schema)** | "Eliminates 90% of JSON-parsing failure modes" |
| **Handler registry with decorators** | "Registration happens at import time, no manual wiring needed" |
| **Async everywhere** | "FastAPI async routes, OpenAI async client, async preprocessing where parallelizable" |

---

## Implementation Journey

### Setting Up the Project Structure

**Bob's Folder Structure Proposal:**

```
backend/
├── app/
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # pydantic-settings
│   ├── api/v1/                    # API routes
│   ├── core/                      # Pipeline, registry, exceptions
│   ├── handlers/                  # Handler implementations
│   ├── ai/                        # OpenAI client, retry logic
│   ├── preprocessing/             # HTML preprocessing stages
│   ├── prompts/                   # Prompt templates by handler
│   ├── schemas/                   # Pydantic models
│   └── utils/                     # Helpers
```

**Implementation Order Bob Suggested:**

1. Schemas + envelope first
2. Handler ABC + registry
3. Echo handler (no-op to validate wiring)
4. Preprocessing pipeline
5. DOM manipulation handler
6. Caching and retry
7. QA and redesign handlers (future)

This order was perfect—each step validated the previous one.

### Building the First Handler (DOM Manipulation)

**The Initial Implementation:**

```python
@register_handler("dom_manipulation")
class DOMManipulationHandler(Handler[DOMManipulationRequest, DOMManipulationResult]):
    """Handler for DOM manipulation via patch operations."""
    
    async def preprocess(self, html: str, params: DOMManipulationRequest) -> ProcessedContext:
        # Clean HTML
        cleaned = clean_html(html)
        
        # Assign element IDs
        soup, id_map = assign_element_ids(cleaned)
        
        # Skeletonize
        skeleton = skeletonize(soup)
        
        return ProcessedContext(
            processed_html=skeleton,
            element_id_map=id_map,
            original_size=len(html),
            processed_size=len(skeleton),
            chunk_count=1,
            metadata={"soup": soup}
        )
```

**Bob's Feedback Loop:**

Bob reviewed each method implementation and suggested improvements:

- "Store the soup in metadata—you'll need it for postprocessing"
- "Log the size reduction—it's useful for debugging token issues"
- "Make id_map a dict[str, str] not dict[int, str]—string keys are safer"

### Implementing Preprocessing Pipeline

**The Cleaner Module:**

Bob wrote the initial `cleaner.py` with comprehensive HTML cleaning:

```python
def clean_html(html: str, preserve_hidden: bool = False) -> str:
    """Clean HTML by removing scripts, comments, base64 images, and noise."""
    soup = BeautifulSoup(html, "lxml")
    
    # Remove script and style content but keep tags as markers
    for tag in soup.find_all(["script", "style"]):
        tag.string = ""
    
    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Strip data: URI images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:"):
            img["src"] = ""
            img["data-stripped"] = "image"
    
    # ... more cleaning logic
```

**Key Insight from Bob:**

> "Keep script and style *tags* as markers even though you empty them. The AI needs to know they exist, and postprocessing needs to preserve them byte-for-byte."

### Creating Prompt Templates

**The System Prompt Evolution:**

Bob iterated on the system prompt through multiple versions:

**v1 (Initial):**
```
You are a web developer that modifies pages by returning patch operations.
```

**v2 (After testing):**
```
You are an expert web developer that edits web pages by emitting a precise 
list of patch operations. You DO NOT return HTML for the whole page.

## How you see the page
You are given a SKELETON of the page, not its full HTML...
```

**v3 (Current - After selector issues):**
```
[Added detailed rules about element IDs, collapsed siblings, and CSS variables]

## Critical rules
1. Never replace/delete <html>, <head>, <body>, <style>, <script>
2. For theme changes, use set_css_var
3. For "all X" requests, use add_css_rule with !important
...
```

Each iteration addressed real issues discovered during testing.

### Debugging and Refinement

**The Selector Stability Problem:**

Early testing revealed that selectors like `div.content > p:nth-child(3)` broke when pages updated. Bob diagnosed the issue:

> "The problem is positional selectors. You need to generate selectors based on stable attributes—IDs, unique classes, data attributes. Avoid :nth-child unless there's no alternative."

Bob then implemented `robust_selector()`:

```python
def robust_selector(element: Tag, soup: BeautifulSoup) -> str:
    """Generate a robust CSS selector for an element."""
    # Prefer ID
    if element.get("id"):
        return f"#{element['id']}"
    
    # Try unique class combination
    classes = element.get("class", [])
    if classes:
        selector = f"{element.name}.{'.'.join(classes)}"
        if len(soup.select(selector)) == 1:
            return selector
    
    # Fall back to path-based selector with stable attributes
    # ...
```

---

## Key Problem-Solving Moments

### Token Budget Challenges and Solutions

**The Problem:**

Initial testing on real websites showed token counts exploding:
- Wikipedia article: 45K tokens (over budget)
- YouTube page: 120K tokens (way over budget)
- News site: 80K tokens (over budget)

**Bob's Solution:**

Bob proposed a three-tier strategy:

1. **Aggressive Cleaning**: Remove more aggressively
2. **Smart Skeletonization**: Collapse repeated structures
3. **Relevance-Based Chunking**: Two-pass processing

```python
# Bob's chunking strategy
if token_count > budget:
    # Pass 1: Send skeleton, ask which sections are relevant
    relevant_sections = await get_relevant_sections(skeleton, user_prompt)
    
    # Pass 2: Send only relevant sections expanded
    expanded = expand_sections(skeleton, relevant_sections)
    return await process_with_ai(expanded, user_prompt)
```

**The Pivot to Anchored Skeleton:**

After further discussion, Bob suggested a better approach:

> "Instead of full skeletonization, use an *anchored skeleton* format. Each element gets a stable anchor ID, and we represent the page as a compact text format showing structure, not full HTML. This is both token-efficient AND gives the model better context."

This led to the current `anchor_skeleton.py` implementation, which reduced token usage by 70-90% while improving model accuracy.

### Selector Stability Issues

**The Crisis:**

During testing, we discovered that patches worked initially but broke after:
- Page re-renders (React/Vue apps)
- Dynamic content loading
- User interactions that modified the DOM

**Bob's Diagnosis:**

> "The issue is that you're generating selectors at preprocessing time, but the DOM changes before patches are applied. You need to either:
> 1. Generate selectors that are resilient to DOM changes, OR
> 2. Apply patches to the live DOM using element references, not selectors"

**The Solution:**

Bob designed a hybrid approach:

1. **Server-side**: Generate anchor IDs and return patches keyed by anchor
2. **Client-side**: Inject a runtime script that:
   - Maps anchors to live DOM elements
   - Applies patches using element references
   - Re-asserts patches after re-renders using MutationObserver

```javascript
// Bob's runtime patch applier (simplified)
class PatchApplier {
    constructor(patches) {
        this.patches = patches;
        this.anchorMap = this.buildAnchorMap();
        this.applyPatches();
        this.watchForReRenders();
    }
    
    buildAnchorMap() {
        // Map anchor IDs to live DOM elements
        const map = new Map();
        document.querySelectorAll('[data-anchor]').forEach(el => {
            map.set(el.dataset.anchor, el);
        });
        return map;
    }
    
    applyPatches() {
        this.patches.forEach(patch => {
            const element = this.anchorMap.get(patch.target);
            if (element) {
                this.applyPatch(element, patch);
            }
        });
    }
    
    watchForReRenders() {
        // Re-apply patches after DOM mutations
        const observer = new MutationObserver(() => {
            this.applyPatches();
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }
}
```

This solved the stability problem completely.

### Full HTML vs Patch-Based Approach Decision

**The Debate:**

Midway through the project, we considered switching to a "full HTML" mode where the AI receives and returns complete HTML.

**Arguments For Full HTML:**
- Simpler architecture
- AI has full context
- Can make any modification

**Arguments Against (Bob's Position):**
- 10-50x larger responses
- Higher token costs
- Harder to validate
- Client needs to compute diffs

**The Decision:**

After implementing both approaches, we kept the patch-based system as primary but added full HTML as an optional mode. Bob's reasoning:

> "Patch-based is better for 90% of use cases—it's faster, cheaper, and more precise. But full HTML is useful for complex redesigns where you need to restructure large sections. Keep both, use feature flags to switch."

### CSS Enhancement Implementation

**The Challenge:**

Users wanted to make styling changes like "make it dark mode" or "make all thumbnails round", but the patch-based approach struggled with site-wide CSS changes.

**Bob's Solution:**

Bob added two new patch operations:

```python
# Set a CSS custom property (for theme changes)
{"op": "set_css_var", "name": "--bg-color", "value": "#1a1a1a"}

# Inject a global CSS rule (for category changes)
{"op": "add_css_rule", "css": "img { border-radius: 50% !important; }"}
```

**The Prompt Update:**

Bob updated the system prompt with specific guidance:

```
For theme/color/dark-mode requests, use set_css_var. The STYLES section 
shows the page's CSS variables. Re-theme by setting those variables—set 
ALL relevant ones (background, text, accents), not just one.

For any request targeting a CATEGORY of elements ("make all thumbnails 
round", "hide every shorts shelf"), emit ONE add_css_rule with a CSS 
selector + declarations using !important.
```

This dramatically improved styling capabilities.

### Performance Optimization

**The Bottleneck:**

Profiling revealed that HTML parsing was taking 40-60% of request time on large pages.

**Bob's Optimization:**

```python
# Before: Parse HTML multiple times
cleaned = clean_html(html)  # Parse 1
soup, id_map = assign_element_ids(cleaned)  # Parse 2
skeleton = skeletonize(soup)  # Parse 3

# After: Parse once, pass soup through pipeline
soup = BeautifulSoup(html, "lxml")  # Parse once
cleaned_soup = clean_html_soup(soup)  # Modify in-place
id_map = assign_element_ids_soup(cleaned_soup)  # Modify in-place
skeleton = skeletonize_soup(cleaned_soup)  # Read from soup
```

This reduced preprocessing time by 60%.

---

## Testing & Validation

### Test Strategy Design

**Bob's Testing Philosophy:**

> "Test at three levels:
> 1. Unit tests for preprocessing functions (fast, isolated)
> 2. Integration tests for handlers (with mocked AI)
> 3. End-to-end tests for the full pipeline (with real AI, behind a flag)"

**The Test Structure:**

```
tests/
├── unit/
│   ├── test_preprocessing.py      # Cleaner, skeletonizer, etc.
│   ├── test_patch_pipeline.py     # Patch application logic
│   └── test_modes.py              # Mode detection
├── integration/
│   ├── test_dom_handler.py        # Full handler with mocked AI
│   └── test_pipeline.py           # Pipeline orchestration
└── fixtures/
    ├── sample.html                # Test HTML files
    └── expected_patches.json      # Expected outputs
```

### Edge Case Identification

**Bob's Edge Case Checklist:**

Bob systematically identified edge cases:

1. **Empty/Malformed HTML**
   ```python
   def test_empty_html():
       with pytest.raises(HTMLParseError):
           clean_html("")
   ```

2. **Massive Pages**
   ```python
   def test_oversize_page():
       huge_html = "<div>" * 100000 + "</div>" * 100000
       with pytest.raises(OversizeError):
           handler.preprocess(huge_html, params)
   ```

3. **Malicious Content**
   ```python
   def test_script_injection():
       patch = {"op": "insert", "html": "<script>alert('xss')</script>"}
       result = handler.postprocess(patch, context)
       assert "<script>" not in result.html
   ```

4. **Selector Edge Cases**
   ```python
   def test_selector_with_special_chars():
       element = soup.find(id="my:weird[id]")
       selector = robust_selector(element, soup)
       assert soup.select_one(selector) == element
   ```

### Validation Pipeline

**Bob's Validation Strategy:**

Bob implemented a multi-stage validation pipeline:

```python
async def postprocess(self, parsed: ResponseT, context: ProcessedContext) -> ResponseT:
    """Apply postprocessing and safety checks."""
    
    # Stage 1: Structural validation
    self._validate_patch_structure(parsed)
    
    # Stage 2: Selector validation
    self._validate_selectors(parsed, context)
    
    # Stage 3: Safety checks
    self._apply_safety_checks(parsed)
    
    # Stage 4: Resolve IDs to selectors
    resolved = self._resolve_element_ids(parsed, context)
    
    return resolved
```

Each stage can fail independently with specific error messages.

---

## Documentation Creation

### Architecture Documentation

**Bob's Documentation Approach:**

Bob wrote the initial `ARCHITECTURE.md` as a design document *before* implementation:

> "Write the architecture doc first. It forces you to think through the design, and it becomes the spec for implementation. Update it as you learn, but start with a clear vision."

**Key Sections Bob Included:**

1. **Core Architectural Decision** - The "why" behind the design
2. **Folder Structure** - Visual map of the codebase
3. **Handler Interface** - The contract all handlers must follow
4. **Request/Response Schemas** - API surface area
5. **HTML Preprocessing & Chunking** - Token optimization strategy
6. **Prompt Management** - How prompts are versioned and loaded
7. **Implementation Order** - Step-by-step build plan

### API Documentation

**Bob's API Doc Strategy:**

Bob insisted on documenting the API through:

1. **Pydantic Models** - Self-documenting schemas
2. **OpenAPI/Swagger** - Auto-generated from FastAPI
3. **Example Requests** - Real curl commands in README
4. **Response Examples** - Actual JSON responses

Example from README:

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "use_case": "dom_manipulation",
    "page_url": "https://example.com",
    "html": "<!DOCTYPE html><html>...</html>",
    "user_prompt": "Make all headings blue"
  }'
```

### This Meta-Documentation

**Why This Document Exists:**

Bob suggested creating this meta-documentation:

> "Document the collaboration itself. It's valuable for:
> - Transparency about AI's role
> - Teaching others how to work with AI
> - Historical record of AI-assisted development in 2026
> - Showing what's possible with human-AI collaboration"

**Structure Bob Suggested:**

1. Introduction (what/why)
2. Project genesis (the beginning)
3. Architecture design (the planning)
4. Implementation (the building)
5. Problem-solving (the challenges)
6. Testing (the validation)
7. Documentation (the explaining)
8. Lessons learned (the wisdom)
9. Code examples (the proof)
10. Future collaboration (the continuation)

---

## Lessons Learned

### What Worked Well with Bob

#### 1. **Iterative Design Discussions**

**Pattern:**
- Human: "I'm thinking about X approach"
- Bob: "Here are the tradeoffs... I suggest Y because..."
- Human: "What about edge case Z?"
- Bob: "Good point, let's handle it like this..."

**Why It Worked:**
Bob provided instant feedback on design decisions, catching issues before implementation.

#### 2. **Code Review and Refinement**

**Pattern:**
- Human implements feature
- Bob reviews code
- Bob suggests improvements (error handling, edge cases, performance)
- Human refines implementation

**Example:**
```python
# Human's initial implementation
def clean_html(html):
    soup = BeautifulSoup(html, "lxml")
    # ... cleaning logic
    return str(soup)

# Bob's suggestion
def clean_html(html: str, preserve_hidden: bool = False) -> str:
    """Clean HTML by removing scripts, comments, and noise.
    
    Args:
        html: Raw HTML content
        preserve_hidden: If True, keep hidden elements (useful for QA)
    
    Returns:
        Cleaned HTML string
    
    Raises:
        HTMLParseError: If HTML cannot be parsed
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        raise HTMLParseError(f"Failed to parse HTML: {e}")
    
    # ... cleaning logic with better error handling
    return str(soup).strip()
```

#### 3. **Comprehensive Documentation**

Bob excelled at writing clear, detailed documentation with:
- Concrete examples
- Rationale for decisions
- Edge case handling
- Future considerations

#### 4. **Problem Decomposition**

Bob consistently broke complex problems into manageable steps:

```
Problem: "How do I handle 500KB HTML pages?"

Bob's Decomposition:
1. Measure the problem (how many tokens?)
2. Clean aggressively (remove noise)
3. Skeletonize (reduce to structure)
4. Chunk if needed (two-pass processing)
5. Validate at each stage
```

#### 5. **Anticipating Future Needs**

Bob designed for extensibility:
- Handler registry for future use cases
- Versioned prompts for A/B testing
- Pluggable preprocessing stages
- Feature flags for gradual rollout

### Effective Collaboration Patterns

#### Pattern 1: **Design First, Implement Second**

```
1. Discuss architecture
2. Write design doc
3. Review and refine design
4. Implement based on design
5. Update design doc with learnings
```

#### Pattern 2: **Test-Driven Development**

```
1. Discuss feature requirements
2. Bob writes test cases
3. Human implements feature
4. Run tests, iterate until passing
5. Bob suggests additional edge cases
```

#### Pattern 3: **Incremental Complexity**

```
1. Start with simplest version
2. Validate it works
3. Add one complexity at a time
4. Test after each addition
5. Refactor when needed
```

#### Pattern 4: **Explicit Error Handling**

Bob insisted on explicit error handling at every stage:

```python
# Bob's pattern
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise CustomError(f"Helpful message: {e}") from e
except Exception as e:
    logger.exception("Unexpected error")
    raise InternalError("Something went wrong") from e
```

### Tips for Working with AI Assistants on Complex Projects

#### 1. **Be Specific About Requirements**

❌ **Bad:** "Make the preprocessing faster"

✅ **Good:** "The preprocessing takes 2 seconds on 500KB HTML. Can we optimize the BeautifulSoup parsing to reduce this to under 500ms?"

#### 2. **Ask for Tradeoffs**

❌ **Bad:** "Should I use approach A or B?"

✅ **Good:** "What are the tradeoffs between approach A and B in terms of performance, maintainability, and token usage?"

#### 3. **Request Rationale**

❌ **Bad:** "Implement feature X"

✅ **Good:** "Implement feature X, and explain why you chose this approach over alternatives"

#### 4. **Iterate on Design Before Implementation**

❌ **Bad:** "Write the code for the handler"

✅ **Good:** "Let's design the handler interface first. What methods should it have and why?"

#### 5. **Validate AI Suggestions**

Bob is excellent, but not infallible. Always:
- Test the code
- Verify edge cases
- Check performance
- Review security implications

#### 6. **Use AI for Boilerplate, Human for Creativity**

**AI Excels At:**
- Writing repetitive code
- Implementing well-known patterns
- Comprehensive error handling
- Documentation
- Test cases

**Humans Excel At:**
- Novel problem-solving
- User experience decisions
- Business logic
- Creative solutions
- Final judgment calls

#### 7. **Maintain Context**

Keep AI informed about:
- Project goals
- Previous decisions
- Current challenges
- Constraints (performance, budget, etc.)

#### 8. **Document the Collaboration**

This document itself is an example—documenting how AI contributed helps:
- Future maintainers understand the codebase
- Other developers learn from your experience
- Provides transparency about AI's role

---

## Code Examples

### Example 1: Handler Registration Pattern

**Bob's Suggestion:**

```python
# handlers/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

RequestT = TypeVar("RequestT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)

class Handler(ABC, Generic[RequestT, ResponseT]):
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    # ... other abstract methods

# core/registry.py
_handler_registry: dict[str, type[Any]] = {}

def register_handler(name: str):
    def decorator(handler_class):
        _handler_registry[name] = handler_class
        return handler_class
    return decorator

# handlers/dom_manipulation.py
@register_handler("dom_manipulation")
class DOMManipulationHandler(Handler[DOMManipulationRequest, DOMManipulationResult]):
    @property
    def name(self) -> str:
        return "dom_manipulation"
    
    # ... implementation
```

**Why This Works:**
- Decorator-based registration is clean and automatic
- Generic types provide type safety
- Registry pattern makes adding handlers trivial

### Example 2: Preprocessing Pipeline

**Before Bob's Refactoring:**

```python
def preprocess(html: str) -> str:
    # Everything in one function
    soup = BeautifulSoup(html, "lxml")
    
    # Remove scripts
    for script in soup.find_all("script"):
        script.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Assign IDs
    for i, element in enumerate(soup.find_all(True)):
        element["data-id"] = f"e{i}"
    
    # Skeletonize
    for element in soup.find_all(string=True):
        if len(element.strip()) > 80:
            element.replace_with("[text]")
    
    return str(soup)
```

**After Bob's Refactoring:**

```python
# preprocessing/cleaner.py
def clean_html(html: str, preserve_hidden: bool = False) -> str:
    """Clean HTML by removing scripts, comments, and noise."""
    # ... focused cleaning logic

# preprocessing/id_anchoring.py
def assign_element_ids(html: str) -> tuple[BeautifulSoup, dict[str, str]]:
    """Assign stable element IDs and return mapping."""
    # ... focused ID assignment logic

# preprocessing/skeletonizer.py
def skeletonize(soup: BeautifulSoup, max_text_length: int = 80) -> str:
    """Replace large text nodes with placeholders."""
    # ... focused skeletonization logic

# handlers/dom_manipulation.py
async def preprocess(self, html: str, params: RequestT) -> ProcessedContext:
    """Orchestrate preprocessing stages."""
    cleaned = clean_html(html)
    soup, id_map = assign_element_ids(cleaned)
    skeleton = skeletonize(soup)
    
    return ProcessedContext(
        processed_html=skeleton,
        element_id_map=id_map,
        # ... metadata
    )
```

**Benefits:**
- Each function has a single responsibility
- Easy to test in isolation
- Can mix and match stages for different handlers
- Clear separation of concerns

### Example 3: Error Handling Hierarchy

**Bob's Exception Design:**

```python
# core/exceptions.py
class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    def __init__(self, message: str, retryable: bool = False, stage: str = "unknown"):
        self.message = message
        self.retryable = retryable
        self.stage = stage
        super().__init__(message)

class PreprocessingError(PipelineError):
    """Errors during HTML preprocessing."""
    def __init__(self, message: str):
        super().__init__(message, retryable=False, stage="preprocessing")

class HTMLParseError(PreprocessingError):
    """HTML parsing failed."""
    pass

class OversizeError(PreprocessingError):
    """HTML exceeds size limits."""
    pass

class AIError(PipelineError):
    """Errors from AI service."""
    pass

class RateLimitError(AIError):
    """AI service rate limit hit."""
    def __init__(self, message: str):
        super().__init__(message, retryable=True, stage="ai_call")

class MalformedResponseError(AIError):
    """AI returned invalid JSON."""
    def __init__(self, message: str):
        super().__init__(message, retryable=True, stage="ai_call")
```

**Usage in Pipeline:**

```python
# core/pipeline.py
try:
    context = await handler.preprocess(html, params)
except PreprocessingError as e:
    return error_response(e)
except Exception as e:
    logger.exception("Unexpected preprocessing error")
    return error_response(InternalError(str(e)))
```

**Benefits:**
- Clear error hierarchy
- Retryable flag guides retry logic
- Stage information helps debugging
- Structured error responses

### Example 4: Prompt Template System

**Bob's Jinja2 Template Approach:**

```jinja2
{# prompts/dom_manipulation/v1/system.j2 #}
You are an expert web developer that edits web pages by emitting patch operations.

## How you see the page

You are given a SKELETON of the page:
```
@<id> <tag>.<class>#<domid> [style=...] "text"
```

## Available operations

{% for op in operations %}
- `{{ op.name }}`: {{ op.description }}
  Example: {{ op.example }}
{% endfor %}

## Critical rules

{% for rule in rules %}
{{ loop.index }}. {{ rule }}
{% endfor %}
```

**Loading and Rendering:**

```python
# prompts/loader.py
class PromptLoader:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader("app/prompts"))
        self.cache = {}
    
    def load_template(self, handler: str, version: str, template: str):
        key = f"{handler}/{version}/{template}"
        if key not in self.cache:
            self.cache[key] = self.env.get_template(key)
        return self.cache[key]
    
    def render(self, handler: str, version: str, template: str, **kwargs):
        tmpl = self.load_template(handler, version, template)
        return tmpl.render(**kwargs)
```

**Benefits:**
- Prompts are separate from code
- Easy to version and A/B test
- Can inject dynamic content
- Cached for performance

### Example 5: Robust Selector Generation

**Bob's Selector Algorithm:**

```python
def robust_selector(element: Tag, soup: BeautifulSoup) -> str:
    """Generate a robust CSS selector for an element.
    
    Priority:
    1. ID (if unique)
    2. Unique class combination
    3. Data attributes
    4. Path-based with stable attributes
    """
    # Try ID
    if element.get("id"):
        elem_id = element["id"]
        # Escape special characters
        elem_id = elem_id.replace(":", "\\:")
        selector = f"#{elem_id}"
        if len(soup.select(selector)) == 1:
            return selector
    
    # Try unique class combination
    classes = element.get("class", [])
    if classes:
        selector = f"{element.name}.{'.'.join(classes)}"
        if len(soup.select(selector)) == 1:
            return selector
    
    # Try data attributes
    for attr in element.attrs:
        if attr.startswith("data-"):
            value = element[attr]
            selector = f"{element.name}[{attr}='{value}']"
            if len(soup.select(selector)) == 1:
                return selector
    
    # Fall back to path-based selector
    path = []
    current = element
    while current and current.name != "[document]":
        # Build selector part with stable attributes
        part = current.name
        if current.get("id"):
            part += f"#{current['id']}"
        elif current.get("class"):
            part += f".{current['class'][0]}"
        path.insert(0, part)
        current = current.parent
    
    return " > ".join(path)
```

**Why This Works:**
- Prioritizes stable selectors (ID, unique classes)
- Falls back gracefully
- Handles special characters
- Validates uniqueness

---

## Future Collaboration

### How Bob Will Help with QA and Redesign Handlers

**QA Handler (Planned):**

Bob has already outlined the QA handler design:

```python
@register_handler("qa")
class QAHandler(Handler[QARequest, QAResponse]):
    """Handler for question answering about page content."""
    
    async def preprocess(self, html: str, params: QARequest) -> ProcessedContext:
        # Different preprocessing: preserve text, drop structure
        cleaned = clean_html(html, preserve_hidden=True)
        # No skeletonization—we need the actual content
        return ProcessedContext(processed_html=cleaned, ...)
    
    async def build_messages(self, context, params, user_prompt):
        # Different prompt: focus on comprehension, not manipulation
        system = load_prompt("qa", "v1", "system.j2")
        user = load_prompt("qa", "v1", "user.j2").render(
            html=context.processed_html,
            question=user_prompt
        )
        return [Message("system", system), Message("user", user)]
    
    async def parse_response(self, raw_response, context):
        # Parse answer + citations
        data = json.loads(raw_response)
        return QAResponse(
            answer=data["answer"],
            citations=[Citation(**c) for c in data["citations"]]
        )
```

**Redesign Handler (Planned):**

Bob's vision for the redesign handler:

```python
@register_handler("redesign")
class RedesignHandler(Handler[RedesignRequest, RedesignResponse]):
    """Handler for full page redesigns with CSS."""
    
    async def preprocess(self, html: str, params: RedesignRequest) -> ProcessedContext:
        # Skeleton-only: model returns CSS, not HTML
        cleaned = clean_html(html)
        skeleton = skeletonize(cleaned, max_text_length=40)
        return ProcessedContext(processed_html=skeleton, ...)
    
    async def build_messages(self, context, params, user_prompt):
        # Prompt includes design system, color theory, accessibility
        system = load_prompt("redesign", "v1", "system.j2").render(
            design_mode=params.design_mode,  # "modern", "minimalist", etc.
            accessibility_level=params.accessibility_level
        )
        # ...
    
    async def parse_response(self, raw_response, context):
        # Parse CSS rules + optional HTML patches
        data = json.loads(raw_response)
        return RedesignResponse(
            css_rules=data["css_rules"],
            html_patches=data.get("html_patches", [])
        )
```

### Ongoing Maintenance and Evolution

**Bob's Maintenance Plan:**

1. **Prompt Iteration**
   - A/B test prompt versions
   - Collect failure cases
   - Refine based on real usage

2. **Performance Optimization**
   - Profile slow requests
   - Optimize preprocessing
   - Cache aggressively

3. **Feature Additions**
   - Visual selector tool
   - Undo/redo system
   - Preset commands

4. **Quality Improvements**
   - Expand test coverage
   - Add integration tests
   - Build evaluation harness

**How to Continue Collaborating with Bob:**

1. **Regular Code Reviews**: Have Bob review PRs for:
   - Code quality
   - Error handling
   - Edge cases
   - Documentation

2. **Design Discussions**: Consult Bob on:
   - New feature architecture
   - Performance optimizations
   - API design
   - Scaling strategies

3. **Problem Solving**: Use Bob for:
   - Debugging complex issues
   - Researching best practices
   - Exploring alternatives
   - Validating approaches

4. **Documentation**: Have Bob help with:
   - API documentation
   - Architecture updates
   - Tutorial creation
   - Example code

---

## Conclusion

Building **DOM Patch Assistant** with Bob demonstrated that human-AI collaboration can produce production-quality software with sophisticated architecture, robust error handling, and comprehensive documentation.

### Key Takeaways

1. **AI as a Force Multiplier**: Bob didn't replace human judgment—he amplified it. Design decisions were collaborative, with Bob providing instant feedback and alternatives.

2. **Architecture Matters**: Bob's insistence on clean architecture (Strategy pattern, handler registry, modular preprocessing) made the system maintainable and extensible.

3. **Documentation is Essential**: Writing design docs before implementation and maintaining them throughout development kept the project on track.

4. **Iteration is Key**: The best solutions emerged through multiple iterations, with Bob providing feedback and refinements at each step.

5. **Test Everything**: Bob's comprehensive test strategy caught issues early and gave confidence in the system.

### The Future of AI-Assisted Development

This project represents a snapshot of AI-assisted development in 2026. As AI capabilities improve, we expect:

- **More sophisticated architecture suggestions**
- **Better understanding of domain-specific patterns**
- **Improved code generation quality**
- **Enhanced debugging capabilities**

But the fundamental pattern will remain: **humans provide vision and judgment, AI provides implementation and refinement**.

### Final Thoughts

Working with Bob on this project was remarkably productive. The combination of human creativity and AI's systematic approach produced a system that neither could have built as effectively alone.

The key to successful AI collaboration is treating the AI as a **skilled junior developer**: capable of excellent implementation, needing guidance on architecture and business logic, and requiring validation of suggestions.

As AI-assisted development becomes mainstream, projects like this will serve as templates for effective human-AI collaboration.

---

**Built with ❤️ and 🤖 by humans and AI working together**

*Last updated: 2026-05-17*

---

## Appendix: Bob's Signature Comments

Throughout the codebase, you'll find Bob's signature at the end of files:

```python
# Made with Bob
```

This simple comment serves as a reminder that this code was created through human-AI collaboration—a new paradigm in software development.

---

*For questions about this collaboration or the project, see the main [README](../README.md) or open an issue on GitHub.*