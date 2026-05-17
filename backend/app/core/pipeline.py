"""Pipeline orchestrator for processing requests through handlers."""
import time
from typing import Any

from ..config import settings
from ..core.exceptions import HandlerDisabledError, PipelineError
from ..core.registry import get_handler
from ..core.tracing import get_logger
from ..handlers.base import Handler
from ..schemas.envelope import ProcessResponse, TimingInfo, UsageInfo

logger = get_logger(__name__)


class Pipeline:
    """
    Orchestrates the processing pipeline for all handlers.
    
    The pipeline is handler-agnostic and follows these stages:
    1. Preprocess - Clean and transform HTML
    2. Build messages - Construct AI prompts
    3. AI call - Send to OpenAI and get response
    4. Parse response - Validate AI output
    5. Postprocess - Apply safety checks and transformations
    """

    def __init__(self, ai_client: Any):
        """
        Initialize pipeline with AI client.
        
        Args:
            ai_client: OpenAI client instance
        """
        self.ai_client = ai_client

    async def process(
        self,
        use_case: str,
        page_url: str,
        html: str,
        user_prompt: str,
        params: dict[str, Any],
        trace_id: str,
    ) -> ProcessResponse:
        """
        Process a request through the appropriate handler.
        
        Args:
            use_case: Handler name to use
            page_url: URL of the page
            html: HTML content
            user_prompt: User's instruction
            params: Handler-specific parameters
            trace_id: Request trace ID
            
        Returns:
            ProcessResponse with results or error
        """
        warnings: list[str] = []
        timing: dict[str, float] = {}

        try:
            # Check if handler is enabled
            if not settings.is_handler_enabled(use_case):
                raise HandlerDisabledError(use_case)

            # Get handler class and instantiate
            handler_class = get_handler(use_case)
            handler: Handler[Any, Any] = handler_class()

            logger.info(
                f"Processing request with handler '{use_case}'",
                extra={
                    "use_case": use_case,
                    "page_url": page_url,
                    "html_size": len(html),
                },
            )

            # Stage 1: Preprocess
            start = time.perf_counter()
            request_obj = handler.request_model(
                page_url=page_url, html=html, user_prompt=user_prompt, params=params
            )
            context = await handler.preprocess(html, request_obj)
            timing["preprocess_ms"] = (time.perf_counter() - start) * 1000

            logger.info(
                "Preprocessing complete",
                extra={
                    "original_size": context.original_size,
                    "processed_size": context.processed_size,
                    "chunk_count": context.chunk_count,
                },
            )

            # Stage 2: Build messages
            messages = await handler.build_messages(context, request_obj, user_prompt)

            # Stage 3: AI call
            start = time.perf_counter()
            ai_response = await self.ai_client.chat_completion(
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                model=handler.model_config.model,
                temperature=handler.model_config.temperature,
                max_completion_tokens=handler.model_config.max_completion_tokens,
                response_format=handler.model_config.response_format,
                reasoning_effort=handler.model_config.reasoning_effort,
            )
            timing["ai_ms"] = (time.perf_counter() - start) * 1000

            # Extract response content and usage
            raw_response = ai_response["choices"][0]["message"]["content"]
            usage_data = ai_response.get("usage", {})

            logger.info(
                "AI call complete",
                extra={
                    "model": handler.model_config.model,
                    "input_tokens": usage_data.get("prompt_tokens", 0),
                    "output_tokens": usage_data.get("completion_tokens", 0),
                },
            )

            # Stage 4: Parse response
            parsed = await handler.parse_response(raw_response, context)

            # Stage 5: Postprocess
            start = time.perf_counter()
            result = await handler.postprocess(parsed, context)
            timing["postprocess_ms"] = (time.perf_counter() - start) * 1000

            # Build response
            timing["total_ms"] = sum(timing.values())

            logger.info(
                "Pipeline complete, returning response",
                extra={
                    "use_case": use_case,
                    "result_bytes": len(result.model_dump_json()),
                    "total_ms": timing["total_ms"],
                },
            )

            return ProcessResponse(
                trace_id=trace_id,
                use_case=use_case,
                status="ok",
                result=result.model_dump(),
                warnings=warnings,
                usage=UsageInfo(
                    input_tokens=usage_data.get("prompt_tokens", 0),
                    output_tokens=usage_data.get("completion_tokens", 0),
                    model=handler.model_config.model,
                ),
                timing_ms=TimingInfo(
                    preprocess_ms=timing.get("preprocess_ms", 0),
                    ai_ms=timing.get("ai_ms", 0),
                    postprocess_ms=timing.get("postprocess_ms", 0),
                    total_ms=timing.get("total_ms", 0),
                ),
            )

        except PipelineError as e:
            logger.error(
                f"Pipeline error in stage '{e.stage}': {e.message}",
                extra={"stage": e.stage, "retryable": e.retryable},
            )
            return ProcessResponse(
                trace_id=trace_id,
                use_case=use_case,
                status="error",
                error={
                    "code": e.__class__.__name__.upper(),
                    "message": e.message,
                    "retryable": e.retryable,
                    "stage": e.stage,
                },
            )

        except Exception as e:
            logger.exception("Unexpected error in pipeline")
            return ProcessResponse(
                trace_id=trace_id,
                use_case=use_case,
                status="error",
                error={
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "retryable": False,
                    "stage": "unknown",
                },
            )

# Made with Bob
