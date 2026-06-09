"""API v1 routes."""
from fastapi import APIRouter, Depends, HTTPException

from ...api.v1.deps import get_current_user, get_pipeline
from ...config import settings
from ...core.exceptions import OversizeError, PipelineError
from ...core.modes import compose_prompt, instruction_for, list_modes
from ...core.pipeline import Pipeline
from ...core.tracing import get_logger, set_trace_id
from ...schemas.envelope import ProcessRequest, ProcessResponse

logger = get_logger(__name__)

router = APIRouter(tags=["v1"])

# Single processing path. Kept as a constant so the pipeline/response shape
# (which still reports which path ran) stays unchanged.
USE_CASE = "dom_manipulation"


@router.post("/process", response_model=ProcessResponse)
async def process_request(
    request: ProcessRequest,
    pipeline: Pipeline = Depends(get_pipeline),
    current_user: dict = Depends(get_current_user),
) -> ProcessResponse:
    """
    Main processing endpoint. Composes the (optional) mode instruction with
    the (optional) user prompt, then runs the single DOM pipeline.

    Args:
        request: Process request (page, prompt, optional mode)
        pipeline: Pipeline instance (injected)
        current_user: Current user (injected, placeholder for auth)

    Returns:
        ProcessResponse with results or error
    """
    # Set trace ID from client or generate new one
    trace_id = set_trace_id(request.client_metadata.trace_id)

    logger.info(
        f"Processing request",
        extra={
            "use_case": USE_CASE,
            "page_url": request.page_url,
            "user_id": current_user.get("user_id"),
        },
    )

    # Compose the effective prompt: mode instruction is the base, the user
    # prompt is a customization layer. Done here (not in the pipeline) so the
    # pipeline/handler stay prompt-agnostic and uncoupled.
    effective_prompt = compose_prompt(
        request.selected_mode, request.user_prompt
    )
    logger.info(
        "Prompt composition",
        extra={
            "selected_mode": request.selected_mode,
            "has_mode_instruction": bool(
                instruction_for(request.selected_mode).strip()
            ),
            "has_user_prompt": bool(request.user_prompt.strip()),
            "effective_prompt_chars": len(effective_prompt),
        },
    )
    if not effective_prompt.strip():
        # Mode selected but its instruction is still blank and no user
        # prompt â€” nothing actionable to send.
        return ProcessResponse(
            trace_id=trace_id,
            use_case=USE_CASE,
            status="error",
            error={
                "code": "EMPTY_PROMPT",
                "message": (
                    f"Selected mode '{request.selected_mode}' has no "
                    "instruction configured and no user prompt was provided."
                ),
                "retryable": False,
                "stage": "validation",
            },
        )

    # Check HTML size limit
    html_size = len(request.html.encode("utf-8"))
    if html_size > settings.max_input_html_bytes:
        logger.warning(f"HTML size {html_size} exceeds limit {settings.max_input_html_bytes}")
        return ProcessResponse(
            trace_id=trace_id,
            use_case=USE_CASE,
            status="error",
            error={
                "code": "OVERSIZE_ERROR",
                "message": f"HTML size {html_size} bytes exceeds limit of {settings.max_input_html_bytes} bytes",
                "retryable": False,
                "stage": "validation",
            },
        )

    # Process through pipeline
    try:
        response = await pipeline.process(
            use_case=USE_CASE,
            page_url=request.page_url,
            html=request.html,
            user_prompt=effective_prompt,
            params=request.params,
            trace_id=trace_id,
            page_identity=request.client_metadata.page_identity,
            page_snapshot=request.client_metadata.page_snapshot,
        )
        return response

    except Exception as e:
        logger.exception("Unexpected error in route handler")
        return ProcessResponse(
            trace_id=trace_id,
            use_case=USE_CASE,
            status="error",
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e),
                "retryable": False,
                "stage": "unknown",
            },
        )


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@router.get("/modes")
async def get_modes() -> dict:
    """Modes for the extension to render. Keys + labels only, no
    instruction text (the backend resolves that from the chosen key)."""
    return {"modes": list_modes()}
