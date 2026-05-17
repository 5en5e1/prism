"""
Handler modules.

This module imports all handler implementations to trigger their registration.
"""
# Import the handler to trigger its @register_handler decorator
from . import dom_manipulation  # noqa: F401

__all__ = ["dom_manipulation"]

# Made with Bob
