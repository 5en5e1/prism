"""QA handler (stub for future implementation)."""
from ..config import settings
from ..core.registry import register_handler
from ..handlers.base import Handler, Message, ModelConfig, ProcessedContext
from ..schemas.qa import QAParams, QARequest, QAResult


@register_handler("qa")
class QAHandler(Handler[QARequest, QAResult]):
    """Handler for question answering (not yet implemented)."""

    @property
    def name(self) -> str:
        return "qa"

    @property
    def request_model(self) -> type[QARequest]:
        return QARequest

    @property
    def response_model(self) -> type[QAResult]:
        return QAResult

    @property
    def model_config(self) -> ModelConfig:
        return ModelConfig(
            model=settings.openai_default_model,
            temperature=0.3,
            max_completion_tokens=2000,
            response_format="json_schema",
        )

    async def preprocess(self, html: str, params: QARequest) -> ProcessedContext:
        raise NotImplementedError("QA handler not yet implemented")

    async def build_messages(
        self, context: ProcessedContext, params: QARequest, user_prompt: str
    ) -> list[Message]:
        raise NotImplementedError("QA handler not yet implemented")

    async def parse_response(self, raw_response: str, context: ProcessedContext) -> QAResult:
        raise NotImplementedError("QA handler not yet implemented")

    async def postprocess(self, parsed: QAResult, context: ProcessedContext) -> QAResult:
        raise NotImplementedError("QA handler not yet implemented")

# Made with Bob
