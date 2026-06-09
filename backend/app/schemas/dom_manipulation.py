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


# ---------------------------------------------------------------------------
# Anchor-id patch protocol (patch-based editing mode)
#
# Every op targets an element by its `data-be` anchor id (the "@N" the model
# saw in the skeleton, passed here as the bare id "N"). The server resolves
# the id against the original DOM and applies the edit, so the model never
# reproduces HTML for unchanged parts of the page.
# ---------------------------------------------------------------------------


class SetTextOp(BaseModel):
    """Replace an element's text content (children are cleared)."""

    op: Literal["set_text"] = "set_text"
    target: str = Field(..., description="Anchor id of the element")
    text: str = Field(..., description="New text content")


class SetAttrOp(BaseModel):
    """Set or remove an attribute (value=null removes it)."""

    op: Literal["set_attr"] = "set_attr"
    target: str = Field(..., description="Anchor id of the element")
    name: str = Field(..., description="Attribute name")
    value: str | None = Field(..., description="Attribute value; null to remove")


class SetStyleOp(BaseModel):
    """Replace the element's inline ``style`` attribute."""

    op: Literal["set_style"] = "set_style"
    target: str = Field(..., description="Anchor id of the element")
    style: str = Field(..., description="Full inline CSS, e.g. 'color:red;'")


class SetCssVarOp(BaseModel):
    """Set a CSS custom property site-wide (non-destructive theming).

    Injects an override into a managed ``<style>`` so the original
    stylesheet is never touched. Beats author ``:root`` and inline vars.
    Best choice for "make the theme/colors X" requests.
    """

    op: Literal["set_css_var"] = "set_css_var"
    name: str = Field(..., description="Variable name, e.g. '--bg' or 'bg'")
    value: str = Field(..., description="Value, e.g. '#ff4fa3'")


class AddCssRuleOp(BaseModel):
    """Inject a site-wide CSS rule (non-destructive, no anchor needed).

    The RIGHT tool for "make all X <visual change>" requests (round all
    thumbnails, hide all shorts, bigger text everywhere). One selector-based
    rule covers every current AND future element, so it is immune to
    virtualization / sibling-collapse / SPA re-render. Injected into a
    managed <style> that overrides author CSS. Prefer this over per-element
    ops whenever the request applies to a category of elements.
    """

    op: Literal["add_css_rule"] = "add_css_rule"
    css: str = Field(
        ...,
        description=(
            "Full CSS rule(s), e.g. "
            "'ytd-thumbnail,.yt-core-image{border-radius:50%!important}'"
        ),
    )


class AddClassOp(BaseModel):
    """Add a CSS class."""

    op: Literal["add_class"] = "add_class"
    target: str = Field(..., description="Anchor id of the element")
    class_name: str = Field(..., description="Class to add")


class RemoveClassOp(BaseModel):
    """Remove a CSS class."""

    op: Literal["remove_class"] = "remove_class"
    target: str = Field(..., description="Anchor id of the element")
    class_name: str = Field(..., description="Class to remove")


class ReplaceInnerOp(BaseModel):
    """Replace an element's inner HTML."""

    op: Literal["replace_inner"] = "replace_inner"
    target: str = Field(..., description="Anchor id of the element")
    html: str = Field(..., description="New inner HTML fragment")


class ReplaceElementOp(BaseModel):
    """Replace the entire element with new HTML."""

    op: Literal["replace_element"] = "replace_element"
    target: str = Field(..., description="Anchor id of the element")
    html: str = Field(..., description="Replacement HTML fragment")


class InsertOp(BaseModel):
    """Insert new HTML relative to an element."""

    op: Literal["insert"] = "insert"
    target: str = Field(..., description="Anchor id of the reference element")
    html: str = Field(..., description="HTML fragment to insert")
    position: Literal["before", "after", "prepend", "append"] = Field(
        ..., description="Where to insert relative to target"
    )


class DeleteOp(BaseModel):
    """Delete an element."""

    op: Literal["delete"] = "delete"
    target: str = Field(..., description="Anchor id of the element to remove")


class MoveOp(BaseModel):
    """Move an element relative to another element."""

    op: Literal["move"] = "move"
    target: str = Field(..., description="Anchor id of the element to move")
    to: str = Field(..., description="Anchor id of the destination element")
    position: Literal["before", "after", "prepend", "append"] = Field(
        ..., description="Where to place target relative to destination"
    )


AnchorPatchOp = (
    SetTextOp
    | SetAttrOp
    | SetStyleOp
    | SetCssVarOp
    | AddCssRuleOp
    | AddClassOp
    | RemoveClassOp
    | ReplaceInnerOp
    | ReplaceElementOp
    | InsertOp
    | DeleteOp
    | MoveOp
)


class DOMPatchResult(BaseModel):
    """Raw patch list returned by the model in patch mode."""

    patches: list[AnchorPatchOp] = Field(
        default_factory=list, description="Ordered list of edits to apply"
    )
    changes_summary: str = Field(
        default="", description="Brief description of the changes"
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
    """Result payload for DOM manipulation.

    ``patches``/``css_vars`` are the primary artifact: the client applies
    them to the LIVE DOM in place (preserving scripts/listeners/SPA state).
    ``modified_html`` is a server-applied fallback for non-JS consumers and
    is lossy on complex pages.
    """

    patches: list[dict] = Field(
        default_factory=list,
        description="Resolved ops with CSS selector + fallback hints",
    )
    css_vars: dict[str, str] = Field(
        default_factory=dict,
        description="CSS custom properties to set site-wide (theming)",
    )
    css_rules: list[str] = Field(
        default_factory=list,
        description="Site-wide CSS rules to inject (selector-based changes)",
    )
    skipped: list[str] = Field(
        default_factory=list, description="Patches that could not be resolved"
    )
    modified_html: str = Field(..., description="Server-applied HTML (fallback)")
    changes_summary: str = Field(..., description="Brief description of changes made")
    original_size: int = Field(..., description="Original HTML size in bytes")
    modified_size: int = Field(..., description="Modified HTML size in bytes")


class DOMManipulationRequest(BaseModel):
    """Full request schema for DOM manipulation (used internally)."""

    page_url: str
    html: str
    user_prompt: str
    params: DOMManipulationParams = Field(default_factory=DOMManipulationParams)
