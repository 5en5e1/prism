"""Schemas for DOM manipulation handler."""
from typing import Literal

from pydantic import BaseModel, Field


# Patch operation types
class MoveOperation(BaseModel):
    """Move an element to a new location."""

    op: Literal["move"] = "move"
    selector: str = Field(..., description="CSS selector of element to move")
    target_selector: str = Field(..., description="CSS selector of target element")
    position: Literal["before", "after", "prepend", "append"] = Field(
        ..., description="Position relative to target"
    )


class InsertOperation(BaseModel):
    """Insert new HTML content."""

    op: Literal["insert"] = "insert"
    html: str = Field(..., description="HTML content to insert")
    target_selector: str = Field(..., description="CSS selector of target element")
    position: Literal["before", "after", "prepend", "append"] = Field(
        ..., description="Position relative to target"
    )


class ReplaceOperation(BaseModel):
    """Replace an element with new HTML."""

    op: Literal["replace"] = "replace"
    selector: str = Field(..., description="CSS selector of element to replace")
    html: str = Field(..., description="Replacement HTML content")


class DeleteOperation(BaseModel):
    """Delete an element."""

    op: Literal["delete"] = "delete"
    selector: str = Field(..., description="CSS selector of element to delete")


class SetAttributeOperation(BaseModel):
    """Set or remove an attribute."""

    op: Literal["set_attr"] = "set_attr"
    selector: str = Field(..., description="CSS selector of target element")
    name: str = Field(..., description="Attribute name")
    value: str | None = Field(..., description="Attribute value (null to remove)")


class AddClassOperation(BaseModel):
    """Add a CSS class to an element."""

    op: Literal["add_class"] = "add_class"
    selector: str = Field(..., description="CSS selector of target element")
    class_name: str = Field(..., description="Class name to add")


class RemoveClassOperation(BaseModel):
    """Remove a CSS class from an element."""

    op: Literal["remove_class"] = "remove_class"
    selector: str = Field(..., description="CSS selector of target element")
    class_name: str = Field(..., description="Class name to remove")


class WrapOperation(BaseModel):
    """Wrap an element with new HTML."""

    op: Literal["wrap"] = "wrap"
    selector: str = Field(..., description="CSS selector of element to wrap")
    wrapper_html: str = Field(..., description="Wrapper HTML (must have single root element)")


class UnwrapOperation(BaseModel):
    """Remove wrapper, keeping inner content."""

    op: Literal["unwrap"] = "unwrap"
    selector: str = Field(..., description="CSS selector of wrapper element to remove")


# Union type for all operations
PatchOperation = (
    MoveOperation
    | InsertOperation
    | ReplaceOperation
    | DeleteOperation
    | SetAttributeOperation
    | AddClassOperation
    | RemoveClassOperation
    | WrapOperation
    | UnwrapOperation
)


class DOMManipulationParams(BaseModel):
    """Parameters specific to DOM manipulation requests."""

    preserve_formatting: bool = Field(
        default=True, description="Preserve original HTML formatting where possible"
    )
    validate_selectors: bool = Field(
        default=True, description="Validate that selectors exist before applying"
    )


class DOMManipulationResult(BaseModel):
    """Result payload for DOM manipulation."""

    patches: list[PatchOperation] = Field(..., description="List of patch operations to apply")
    element_count: int = Field(..., description="Number of elements in processed HTML")
    applied_skeletonization: bool = Field(
        ..., description="Whether HTML was skeletonized during processing"
    )


class DOMManipulationRequest(BaseModel):
    """Full request schema for DOM manipulation (used internally)."""

    page_url: str
    html: str
    user_prompt: str
    params: DOMManipulationParams = Field(default_factory=DOMManipulationParams)

# Made with Bob
