"""API v1 routes."""
from fastapi import APIRouter, Depends, HTTPException

from ...api.v1.deps import get_current_user, get_pipeline
from ...config import settings
from ...core.exceptions import OversizeError, PipelineError
from ...core.pipeline import Pipeline
from ...core.tracing import get_logger, set_trace_id
from ...schemas.envelope import ProcessRequest, ProcessResponse

logger = get_logger(__name__)

router = APIRouter(tags=["v1"])


@router.post("/process", response_model=ProcessResponse)
async def process_request(
    request: ProcessRequest,
    pipeline: Pipeline = Depends(get_pipeline),
    current_user: dict = Depends(get_current_user),
) -> ProcessResponse:
    """
    Main processing endpoint for all use cases.
    
    Args:
        request: Process request with use_case discriminator
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
            "use_case": request.use_case,
            "page_url": request.page_url,
            "user_id": current_user.get("user_id"),
        },
    )

    # Check HTML size limit
    html_size = len(request.html.encode("utf-8"))
    if html_size > settings.max_input_html_bytes:
        logger.warning(f"HTML size {html_size} exceeds limit {settings.max_input_html_bytes}")
        return ProcessResponse(
            trace_id=trace_id,
            use_case=request.use_case,
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
            use_case=request.use_case,
            page_url=request.page_url,
            html=request.html,
            user_prompt=request.user_prompt,
            params=request.params,
            trace_id=trace_id,
        )
        return response

    except Exception as e:
        logger.exception("Unexpected error in route handler")
        return ProcessResponse(
            trace_id=trace_id,
            use_case=request.use_case,
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

# Made with Bob
