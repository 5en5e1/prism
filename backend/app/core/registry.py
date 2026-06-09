"""Handler registry with decorator-based registration."""
from typing import Any, Callable, TypeVar

from ..core.exceptions import HandlerNotFoundError

# Type variable for handler classes
T = TypeVar("T")

# Global registry mapping handler names to handler classes
_handler_registry: dict[str, type[Any]] = {}


def register_handler(name: str) -> Callable[[type[T]], type[T]]:
    """
    Decorator to register a handler class in the global registry.
    
    Usage:
        @register_handler("dom_manipulation")
        class DOMManipulationHandler(Handler):
            ...
    """

    def decorator(handler_class: type[T]) -> type[T]:
        if name in _handler_registry:
            raise ValueError(f"Handler '{name}' is already registered")
        _handler_registry[name] = handler_class
        return handler_class

    return decorator


def get_handler(name: str) -> type[Any]:
    """
    Get a handler class from the registry by name.
    
    Raises:
        HandlerNotFoundError: If handler is not registered
    """
    if name not in _handler_registry:
        raise HandlerNotFoundError(name)
    return _handler_registry[name]


def list_handlers() -> list[str]:
    """List all registered handler names."""
    return list(_handler_registry.keys())


def is_handler_registered(name: str) -> bool:
    """Check if a handler is registered."""
    return name in _handler_registry
