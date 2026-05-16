"""DOM manipulation handler implementation."""
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from ..core.exceptions import MalformedResponseError, PostprocessError, ValidationError
from ..core.registry import register_handler
from ..core.tracing import get_logger
from ..handlers.base import Handler, Message, ModelConfig, ProcessedContext
from ..preprocessing.cleaner import clean_html
from ..preprocessing.id_anchoring import assign_element_ids
from ..preprocessing.skeletonizer import skeletonize_html
from ..prompts.loader import get_prompt_loader
from ..schemas.dom_manipulation import (
    DOMManipulationRequest,
    DOMManipulationResult,
    SetAttributeOperation,
)

logger = get_logger(__name__)


@register_handler("dom_manipulation")
class DOMManipulationHandler(Handler[DOMManipulationRequest, DOMManipulationResult]):
    """Handler for DOM manipulation tasks."""

    @property
    def name(self) -> str:
        return "dom_manipulation"

    @property
    def request_model(self) -> type[DOMManipulationRequest]:
        return DOMManipulationRequest

    @property
    def response_model(self) -> type[DOMManipulationResult]:
        return DOMManipulationResult

    @property
    def model_config(self) -> ModelConfig:
        return ModelConfig(
            model="gpt-4o",
            temperature=0.2,
            max_tokens=4000,
            response_format="json_schema",
        )

    async def preprocess(
        self, html: str, params: DOMManipulationRequest
    ) -> ProcessedContext:
        """
        Preprocess HTML for DOM manipulation.
        
        Steps:
        1. Clean HTML (remove scripts, comments, etc.)
        2. Assign element IDs
        3. Skeletonize if needed (replace long text with placeholders)
        """
        logger.info("Starting preprocessing for DOM manipulation")

        # Stage 1: Clean HTML
        cleaned_html = clean_html(html, preserve_hidden=False)
        original_size = len(html)
        cleaned_size = len(cleaned_html)

        logger.info(
            f"Cleaned HTML: {original_size} -> {cleaned_size} bytes "
            f"({100 * (1 - cleaned_size / original_size):.1f}% reduction)"
        )

        # Stage 2: Assign element IDs
        html_with_ids, element_id_map = assign_element_ids(cleaned_html)

        # Stage 3: Skeletonize for structure-focused tasks
        skeletonized_html = skeletonize_html(html_with_ids, max_text_length=80)
        applied_skeletonization = len(skeletonized_html) < len(html_with_ids)

        processed_size = len(skeletonized_html)

        logger.info(
            f"Preprocessing complete: {len(element_id_map)} elements, "
            f"skeletonization={'applied' if applied_skeletonization else 'skipped'}"
        )

        return ProcessedContext(
            processed_html=skeletonized_html,
            element_id_map=element_id_map,
            original_size=original_size,
            processed_size=processed_size,
            chunk_count=1,
            metadata={
                "applied_skeletonization": applied_skeletonization,
                "element_count": len(element_id_map),
            },
        )

    async def build_messages(
        self, context: ProcessedContext, params: DOMManipulationRequest, user_prompt: str
    ) -> list[Message]:
        """Build OpenAI messages using Jinja templates."""
        loader = get_prompt_loader()

        # Render system prompt
        system_content = loader.render_template("dom_manipulation", "system")
        if not system_content:
            raise ValueError("System template not found for dom_manipulation")

        # Render user prompt with context
        user_content = loader.render_template(
            "dom_manipulation",
            "user",
            user_prompt=user_prompt,
            processed_html=context.processed_html,
        )
        if not user_content:
            raise ValueError("User template not found for dom_manipulation")

        return [
            Message(role="system", content=system_content),
            Message(role="user", content=user_content),
        ]

    async def parse_response(
        self, raw_response: str, context: ProcessedContext
    ) -> DOMManipulationResult:
        """Parse and validate AI response."""
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise MalformedResponseError(f"Invalid JSON: {e}")

        # Validate against schema
        try:
            result = DOMManipulationResult(**data)
        except Exception as e:
            raise ValidationError(f"Response validation failed: {e}")

        return result

    async def postprocess(
        self, parsed: DOMManipulationResult, context: ProcessedContext
    ) -> DOMManipulationResult:
        """
        Apply safety checks and transformations.
        
        1. Validate selectors reference existing elements
        2. Sanitize HTML in insert/replace operations
        """
        logger.info(f"Postprocessing {len(parsed.patches)} patch operations")

        # Sanitize HTML in operations
        for patch in parsed.patches:
            # Check insert operations
            if hasattr(patch, "html"):
                html_content = getattr(patch, "html")
                if not self._is_safe_html(html_content):
                    raise PostprocessError(
                        f"Unsafe HTML detected in {patch.op} operation: {html_content[:100]}"
                    )

            # Check wrapper HTML
            if hasattr(patch, "wrapper_html"):
                wrapper = getattr(patch, "wrapper_html", None)
                if wrapper and not self._is_safe_html(wrapper):
                    raise PostprocessError(
                        f"Unsafe HTML detected in wrapper: {wrapper[:100]}"
                    )

            # Validate selectors reference existing elements
            if hasattr(patch, "selector"):
                selector = getattr(patch, "selector")
                if not self._validate_selector(selector, context.element_id_map):
                    logger.warning(f"Selector may not exist: {selector}")

            if hasattr(patch, "target_selector"):
                target = getattr(patch, "target_selector")
                if not self._validate_selector(target, context.element_id_map):
                    logger.warning(f"Target selector may not exist: {target}")

        logger.info("Postprocessing complete")
        return parsed

    def _is_safe_html(self, html: str) -> bool:
        """Check if HTML is safe (no scripts, event handlers, etc.)."""
        html_lower = html.lower()

        # Check for script tags
        if "<script" in html_lower:
            return False

        # Check for event handlers
        if re.search(r'\bon\w+\s*=', html_lower):
            return False

        # Check for javascript: URLs
        if "javascript:" in html_lower:
            return False

        # Check for iframes (could be more sophisticated)
        if "<iframe" in html_lower:
            return False

        return True

    def _validate_selector(self, selector: str, element_id_map: dict[str, str]) -> bool:
        """Validate that a selector references an existing element ID."""
        # Extract element ID from selector like [data-element-id='e5']
        match = re.search(r"data-element-id=['\"](\w+)['\"]", selector)
        if match:
            element_id = match.group(1)
            return element_id in element_id_map
        return True  # If not using our ID format, assume it's valid

# Made with Bob
