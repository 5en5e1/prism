"""Trace ID propagation and structured logging."""
import logging
import uuid
from contextvars import ContextVar
from typing import Any

# Context variable for trace ID
_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def generate_trace_id() -> str:
    """Generate a new trace ID."""
    return str(uuid.uuid4())


def set_trace_id(trace_id: str | None = None) -> str:
    """Set the trace ID for the current context. Returns the trace ID."""
    if trace_id is None:
        trace_id = generate_trace_id()
    _trace_id_var.set(trace_id)
    return trace_id


def get_trace_id() -> str | None:
    """Get the trace ID for the current context."""
    return _trace_id_var.get()


class TraceLogger:
    """Logger that automatically includes trace_id in all log records."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """Internal log method that adds trace_id."""
        trace_id = get_trace_id()
        extra = kwargs.pop("extra", {})
        if trace_id:
            extra["trace_id"] = trace_id
        self.logger.log(level, msg, extra=extra, **kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message with trace_id."""
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message with trace_id."""
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message with trace_id."""
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message with trace_id."""
        self._log(logging.ERROR, msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception with trace_id."""
        trace_id = get_trace_id()
        extra = kwargs.pop("extra", {})
        if trace_id:
            extra["trace_id"] = trace_id
        self.logger.exception(msg, extra=extra, **kwargs)


def get_logger(name: str) -> TraceLogger:
    """Get a trace-aware logger."""
    return TraceLogger(name)

# Made with Bob
