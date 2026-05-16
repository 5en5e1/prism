"""
Handler modules.

This module imports all handler implementations to trigger their registration.
"""
# Import all handlers to trigger @register_handler decorators
from . import dom_manipulation, qa, redesign  # noqa: F401

__all__ = ["dom_manipulation", "qa", "redesign"]

# Made with Bob
