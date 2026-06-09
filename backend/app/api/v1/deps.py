"""Dependency injection for API routes."""
from typing import Any

from fastapi import Request

from ...ai.client import AIClient
from ...core.pipeline import Pipeline


async def get_pipeline(request: Request) -> Pipeline:
    """
    Get the pipeline instance from app state.
    
    Args:
        request: FastAPI request
        
    Returns:
        Pipeline instance
    """
    return request.app.state.pipeline


async def get_current_user() -> dict[str, Any]:
    """
    Get current user (placeholder for future auth).
    
    Returns:
        Anonymous user dict
    """
    return {"user_id": "anonymous", "authenticated": False}
