"""Redesign handler (stub for future implementation)."""
from ..core.registry import register_handler
from ..handlers.base import Handler, Message, ModelConfig, ProcessedContext
from ..schemas.redesign import RedesignParams, RedesignRequest, RedesignResult


@register_handler("redesign")
class RedesignHandler(Handler[RedesignRequest, RedesignResult]):
    """Handler for page redesign (not yet implemented)."""

    @property
    def name(self) -> str:
        return "redesign"

    @property
    def request_model(self) -> type[RedesignRequest]:
        return RedesignRequest

    @property
    def response_model(self) -> type[RedesignResult]:
        return RedesignResult

    @property
    def model_config(self) -> ModelConfig:
        return ModelConfig(
            model="gpt-4o",
            temperature=0.5,
            max_tokens=4000,
            response_format="json_schema",
        )

    async def preprocess(self, html: str, params: RedesignRequest) -> ProcessedContext:
        raise NotImplementedError("Redesign handler not yet implemented")

    async def build_messages(
        self, context: ProcessedContext, params: RedesignRequest, user_prompt: str
    ) -> list[Message]:
        raise NotImplementedError("Redesign handler not yet implemented")

    async def parse_response(
        self, raw_response: str, context: ProcessedContext
    ) -> RedesignResult:
        raise NotImplementedError("Redesign handler not yet implemented")

    async def postprocess(
        self, parsed: RedesignResult, context: ProcessedContext
    ) -> RedesignResult:
        raise NotImplementedError("Redesign handler not yet implemented")

# Made with Bob
