"""Base handler interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


@dataclass
class ModelConfig:
    """Configuration for the AI model."""

    model: str
    temperature: float
    max_completion_tokens: int  # Changed from max_tokens for GPT-5 compatibility
    response_format: str | None = None  # "json_schema" for structured outputs
    # Reasoning-model effort: "minimal" | "low" | "medium" | "high".
    # Lower = far fewer reasoning tokens. Ignored by non-reasoning models.
    reasoning_effort: str | None = None


@dataclass
class ProcessedContext:
    """Context object returned by preprocessing."""

    processed_html: str
    element_id_map: dict[str, str]  # element_id -> CSS selector
    original_size: int
    processed_size: int
    chunk_count: int
    metadata: dict[str, Any]


@dataclass
class Message:
    """OpenAI chat message."""

    role: str  # "system", "user", "assistant"
    content: str


# Type variables for request/response models
RequestT = TypeVar("RequestT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


class Handler(ABC, Generic[RequestT, ResponseT]):
    """
    Abstract base class for use case handlers.
    
    Each handler implements a complete pipeline for a specific use case:
    - Preprocessing: clean and transform HTML
    - Prompt building: construct OpenAI messages
    - Response parsing: validate and transform AI output
    - Postprocessing: apply safety checks and transformations
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Handler name used for registry lookup."""
        pass

    @property
    @abstractmethod
    def request_model(self) -> type[RequestT]:
        """Pydantic model for handler-specific request parameters."""
        pass

    @property
    @abstractmethod
    def response_model(self) -> type[ResponseT]:
        """Pydantic model for handler-specific response."""
        pass

    @property
    @abstractmethod
    def model_config(self) -> ModelConfig:
        """Configuration for the AI model."""
        pass

    @abstractmethod
    async def preprocess(self, html: str, params: RequestT) -> ProcessedContext:
        """
        Preprocess HTML for this use case.
        
        Args:
            html: Raw HTML content
            params: Handler-specific parameters
            
        Returns:
            ProcessedContext with cleaned HTML and metadata
        """
        pass

    @abstractmethod
    async def build_messages(
        self, context: ProcessedContext, params: RequestT, user_prompt: str
    ) -> list[Message]:
        """
        Build OpenAI chat messages from context and user prompt.
        
        Args:
            context: Preprocessed context
            params: Handler-specific parameters
            user_prompt: User's natural language instruction
            
        Returns:
            List of messages for OpenAI API
        """
        pass

    @abstractmethod
    async def parse_response(self, raw_response: str, context: ProcessedContext) -> ResponseT:
        """
        Parse and validate AI response.
        
        Args:
            raw_response: Raw response from OpenAI
            context: Preprocessed context for validation
            
        Returns:
            Validated response model
            
        Raises:
            MalformedResponseError: If response cannot be parsed
            ValidationError: If response fails validation
        """
        pass

    @abstractmethod
    async def postprocess(self, parsed: ResponseT, context: ProcessedContext) -> ResponseT:
        """
        Apply postprocessing and safety checks.
        
        Args:
            parsed: Parsed response from AI
            context: Preprocessed context
            
        Returns:
            Final response with safety checks applied
            
        Raises:
            PostprocessError: If postprocessing fails
        """
        pass
