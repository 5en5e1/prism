"""Schemas for redesign handler (stub for future implementation)."""
from pydantic import BaseModel, Field

from .dom_manipulation import PatchOperation


class RedesignParams(BaseModel):
    """Parameters specific to redesign requests."""

    target_framework: str | None = Field(
        None, description="Target CSS framework (e.g., 'tailwind', 'bootstrap')"
    )
    preserve_functionality: bool = Field(
        default=True, description="Preserve existing JavaScript functionality"
    )
    responsive: bool = Field(default=True, description="Ensure responsive design")


class RedesignResult(BaseModel):
    """Result payload for redesign."""

    css_rules: str = Field(..., description="Generated CSS rules")
    html_patches: list[PatchOperation] = Field(
        default_factory=list, description="Optional HTML structure changes"
    )
    framework_used: str | None = Field(None, description="CSS framework used if any")
    breakpoints: dict[str, str] = Field(
        default_factory=dict, description="Responsive breakpoints defined"
    )


class RedesignRequest(BaseModel):
    """Full request schema for redesign (used internally)."""

    page_url: str
    html: str
    user_prompt: str
    params: RedesignParams = Field(default_factory=RedesignParams)

# Made with Bob
