"""Exception hierarchy for the pipeline."""


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    def __init__(self, message: str, stage: str = "unknown", retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.retryable = retryable


# Preprocessing errors
class PreprocessingError(PipelineError):
    """Base class for preprocessing errors."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, stage="preprocessing", retryable=retryable)


class HTMLParseError(PreprocessingError):
    """Failed to parse HTML."""

    pass


class OversizeError(PreprocessingError):
    """Input HTML exceeds size limits."""

    pass


# AI errors
class AIError(PipelineError):
    """Base class for AI-related errors."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message, stage="ai_call", retryable=retryable)


class RateLimitError(AIError):
    """OpenAI rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, retryable=True)


class TimeoutError(AIError):
    """OpenAI request timed out."""

    def __init__(self, message: str = "Request timed out"):
        super().__init__(message, retryable=True)


class ContentFilterError(AIError):
    """Content was filtered by OpenAI."""

    def __init__(self, message: str = "Content filtered"):
        super().__init__(message, retryable=False)


class MalformedResponseError(AIError):
    """AI response could not be parsed."""

    def __init__(self, message: str = "Malformed AI response"):
        super().__init__(message, retryable=False)


# Handler errors
class HandlerError(PipelineError):
    """Base class for handler errors."""

    def __init__(self, message: str, stage: str = "handler", retryable: bool = False):
        super().__init__(message, stage=stage, retryable=retryable)


class HandlerNotFoundError(HandlerError):
    """Requested handler not found in registry."""

    def __init__(self, handler_name: str):
        super().__init__(f"Handler '{handler_name}' not found", retryable=False)
        self.handler_name = handler_name


class HandlerDisabledError(HandlerError):
    """Handler is disabled via feature flag."""

    def __init__(self, handler_name: str):
        super().__init__(f"Handler '{handler_name}' is disabled", retryable=False)
        self.handler_name = handler_name


class ValidationError(HandlerError):
    """Request or response validation failed."""

    def __init__(self, message: str):
        super().__init__(message, stage="validation", retryable=False)


class PostprocessError(HandlerError):
    """Postprocessing failed."""

    def __init__(self, message: str):
        super().__init__(message, stage="postprocess", retryable=False)

# Made with Bob
