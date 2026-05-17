"""Application configuration using pydantic-settings."""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_default_model: str = Field(..., description="OpenAI model (required, set via .env)")
    openai_timeout_s: int = Field(
        default=600,
        description=(
            "OpenAI request timeout in seconds. Generating a full HTML "
            "document on a reasoning model can take minutes; 60s is far "
            "too short and guarantees a timeout."
        ),
    )
    openai_reasoning_effort: Literal[
        "none", "low", "medium", "high", "xhigh"
    ] = Field(
        default="medium",
        description=(
            "Reasoning effort for reasoning models (gpt-5*, o1/o3/o4). "
            "gpt-5.5 supports: none, low, medium, high, xhigh (note: no "
            "'minimal'). Higher effort spends more reasoning tokens; on a "
            "large HTML rewrite high/xhigh can run away. Ignored by "
            "non-reasoning models."
        ),
    )
    openai_max_completion_tokens: int = Field(
        default=32_000,
        description=(
            "Max completion tokens for handlers that emit a full HTML document. "
            "On reasoning models (gpt-5*, o1/o3/o4) this budget is shared between "
            "reasoning and visible output, so it must be large enough for both."
        ),
    )
    dom_skeleton_token_budget: int = Field(
        default=60_000,
        description=(
            "Max tokens for the anchored DOM skeleton sent to the model in "
            "patch mode. Sibling runs are collapsed and deep subtrees pruned "
            "to fit; if the page still exceeds this, the request is rejected "
            "rather than silently truncated."
        ),
    )
    dom_skeleton_compact: bool = Field(
        default=True,
        description=(
            "Compact skeleton profile (tighter text/class/attr limits and "
            "more aggressive sibling collapse). Cuts model input tokens "
            "with no effect on patch-apply correctness (selectors come from "
            "the id_map, not the skeleton). Set DOM_SKELETON_COMPACT=false "
            "to restore the exact prior verbose skeleton if targeting "
            "quality regresses."
        ),
    )
    dom_emit_server_html: bool = Field(
        default=False,
        description=(
            "Also return a full server-applied 'modified_html' fallback. "
            "Off by default: the extension applies 'patches' to the live "
            "DOM, and building this on every request runs a slow "
            "reserialize + bloats the response on large pages (can stall "
            "the extension's result delivery). Enable only for non-JS "
            "consumers that need finished HTML."
        ),
    )
    dom_apply_mode: Literal["inject", "server"] = Field(
        default="server",
        description=(
            "How edits are applied. 'inject' (default): return the original "
            "HTML byte-for-byte plus a runtime <script> that patches the "
            "live post-JS DOM and persists across re-renders (works for "
            "static, dynamic, animated, SPA sites). 'server': apply patches "
            "to a parsed tree and reserialize (lossy on complex pages; only "
            "for non-JS/static consumers)."
        ),
    )
    dom_max_patch_tokens: int = Field(
        default=8_000,
        description=(
            "Max completion tokens for the patch-list response. Patches are "
            "small (intent, not full HTML), so this stays low even for huge "
            "pages."
        ),
    )

    # Input Limits
    max_input_html_bytes: int = Field(
        default=10_485_760, description="Maximum HTML input size (10MB)"
    )
    max_tokens_per_request: int = Field(
        default=120_000, description="Maximum tokens per request (GPT-4o supports 128K)"
    )

    # Caching
    cache_backend: Literal["memory", "redis", "none"] = Field(
        default="memory", description="Cache backend type"
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )

    # CORS
    cors_allowed_origins: list[str] = Field(
        default=["chrome-extension://*"], description="Allowed CORS origins"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: Literal["json", "text"] = Field(
        default="json", description="Log output format"
    )

    # Rate Limiting
    rate_limit_per_minute_per_ip: int = Field(
        default=60, description="Rate limit per IP per minute"
    )


# Global settings instance
settings = Settings()

# Made with Bob
