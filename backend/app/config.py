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
    openai_default_model: str = Field(default="gpt-4o", description="Default OpenAI model")
    openai_timeout_s: int = Field(default=60, description="OpenAI request timeout in seconds")

    # Input Limits
    max_input_html_bytes: int = Field(
        default=5_242_880, description="Maximum HTML input size (5MB)"
    )
    max_tokens_per_request: int = Field(
        default=100_000, description="Maximum tokens per request"
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

    # Feature Flags
    feature_flag_dom_manipulation: bool = Field(
        default=True, description="Enable DOM manipulation handler"
    )
    feature_flag_qa: bool = Field(default=False, description="Enable QA handler")
    feature_flag_redesign: bool = Field(default=False, description="Enable redesign handler")

    def is_handler_enabled(self, handler_name: str) -> bool:
        """Check if a handler is enabled via feature flags."""
        flag_map = {
            "dom_manipulation": self.feature_flag_dom_manipulation,
            "qa": self.feature_flag_qa,
            "redesign": self.feature_flag_redesign,
        }
        return flag_map.get(handler_name, False)


# Global settings instance
settings = Settings()

# Made with Bob
