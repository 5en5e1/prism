"""Shared request/response envelope schemas."""
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..core.modes import is_known_mode


class ClientMetadata(BaseModel):
    """Client metadata included in requests."""

    extension_version: str | None = Field(None, description="Extension version string")
    trace_id: str | None = Field(None, description="Optional client-provided trace ID")


class ProcessRequest(BaseModel):
    """Request envelope for the /api/v1/process endpoint.

    There is a single processing path (DOM manipulation handles every
    request), so there is no use-case selector. Unknown fields are ignored
    by default, so older clients still sending ``use_case`` keep working.
    """

    page_url: str = Field(..., description="URL of the page being processed")
    html: str = Field(..., description="HTML content to process")
    user_prompt: str = Field(
        default="", description="User's natural language instruction (optional if a mode is selected)"
    )
    selected_mode: str | None = Field(
        default=None,
        description="Mode key (from GET /modes), or null for no mode. The "
        "backend resolves its instruction; clients never send instruction text.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Handler-specific parameters"
    )
    client_metadata: ClientMetadata = Field(
        default_factory=ClientMetadata, description="Client metadata"
    )

    @model_validator(mode="after")
    def _validate_mode_and_prompt(self) -> "ProcessRequest":
        if not is_known_mode(self.selected_mode):
            raise ValueError(
                f"Unknown selected_mode '{self.selected_mode}'. It must match "
                "a mode prompt file on the backend, or be null."
            )
        # Same rule the extension enforces: with no mode there must be a
        # prompt. (Mode + blank instruction + blank prompt is rejected later
        # at composition time with a precise message.)
        if self.selected_mode is None and not self.user_prompt.strip():
            raise ValueError(
                "user_prompt is required when no mode is selected."
            )
        return self


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
