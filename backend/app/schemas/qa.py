"""Schemas for QA handler (stub for future implementation)."""
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation reference in QA response."""

    element_id: str = Field(..., description="Element ID from preprocessing")
    selector: str = Field(..., description="CSS selector for the element")
    snippet: str = Field(..., description="Text snippet from the element")


class QAParams(BaseModel):
    """Parameters specific to QA requests."""

    max_citations: int = Field(default=5, description="Maximum number of citations to return")
    include_context: bool = Field(
        default=True, description="Include surrounding context in citations"
    )


class QAResult(BaseModel):
    """Result payload for QA."""

    answer: str = Field(..., description="Natural language answer to the question")
    citations: list[Citation] = Field(
        default_factory=list, description="Source citations from the HTML"
    )
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence score if available"
    )


class QARequest(BaseModel):
    """Full request schema for QA (used internally)."""

    page_url: str
    html: str
    user_prompt: str
    params: QAParams = Field(default_factory=QAParams)

# Made with Bob
