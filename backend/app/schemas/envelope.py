"""Shared request/response envelope schemas."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class ClientMetadata(BaseModel):
    """Client metadata included in requests."""

    extension_version: str | None = Field(None, description="Extension version string")
    trace_id: str | None = Field(None, description="Optional client-provided trace ID")


class ProcessRequest(BaseModel):
    """Request envelope for the /api/v1/process endpoint."""

    use_case: Literal["dom_manipulation", "qa", "redesign"] = Field(
        ..., description="Use case handler to invoke"
    )
    page_url: str = Field(..., description="URL of the page being processed")
    html: str = Field(..., description="HTML content to process")
    user_prompt: str = Field(..., description="User's natural language instruction")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Use-case-specific parameters"
    )
    client_metadata: ClientMetadata = Field(
        default_factory=ClientMetadata, description="Client metadata"
    )


class UsageInfo(BaseModel):
    """Token usage information."""

    input_tokens: int = Field(..., description="Number of input tokens")
    output_tokens: int = Field(..., description="Number of output tokens")
    model: str = Field(..., description="Model used for generation")


class TimingInfo(BaseModel):
    """Timing breakdown for request processing."""

    preprocess_ms: float = Field(..., description="Preprocessing time in milliseconds")
    ai_ms: float = Field(..., description="AI call time in milliseconds")
    postprocess_ms: float = Field(..., description="Postprocessing time in milliseconds")
    total_ms: float = Field(..., description="Total time in milliseconds")


class ErrorDetail(BaseModel):
    """Error details in error responses."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    retryable: bool = Field(..., description="Whether the error is retryable")
    stage: str = Field(..., description="Pipeline stage where error occurred")


class ProcessResponse(BaseModel):
    """Response envelope for the /api/v1/process endpoint."""

    trace_id: str = Field(..., description="Trace ID for request tracking")
    use_case: str = Field(..., description="Use case that was executed")
    status: Literal["ok", "partial", "error"] = Field(..., description="Response status")
    result: dict[str, Any] | None = Field(None, description="Use-case-specific result payload")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")
    usage: UsageInfo | None = Field(None, description="Token usage information")
    timing_ms: TimingInfo | None = Field(None, description="Timing breakdown")
    error: ErrorDetail | None = Field(None, description="Error details if status is error")

# Made with Bob
