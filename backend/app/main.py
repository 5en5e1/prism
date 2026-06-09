"""FastAPI application entry point."""
import logging
import re
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .ai.client import AIClient
from .api.v1.routes import router as v1_router
from .config import settings
from .core.pipeline import Pipeline
from .core.tracing import get_logger

# Import handlers to trigger registration
from . import handlers  # noqa: F401

logger = get_logger(__name__)


def setup_logging() -> None:
    """Configure logging based on settings."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    if settings.log_format == "json":
        # In production, use structured JSON logging
        logging.basicConfig(
            level=log_level,
            format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
            stream=sys.stdout,
        )
    else:
        # In development, use human-readable format
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown.
    
    Startup:
    - Initialize AI client
    - Create pipeline
    - Load prompt templates
    
    Shutdown:
    - Close AI client
    """
    logger.info("Starting up application")

    # Initialize AI client
    ai_client = AIClient()
    app.state.ai_client = ai_client

    # Initialize pipeline
    pipeline = Pipeline(ai_client)
    app.state.pipeline = pipeline

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application")
    await ai_client.close()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging()

    app = FastAPI(
        title="Prism API",
        description="Backend API for Prism page transformations",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware.
    #
    # Starlette matches allow_origins by EXACT string only -- it has no glob
    # support. A configured value like "chrome-extension://*" would never
    # match a real origin ("chrome-extension://<id>"), so responses ship
    # without Access-Control-Allow-Origin and the browser silently discards
    # them (the extension's fetch never resolves -- looks like a hang).
    # Translate any wildcard pattern into allow_origin_regex; keep literals
    # in allow_origins.
    exact_origins: list[str] = []
    regex_parts: list[str] = []
    for origin in settings.cors_allowed_origins:
        if "*" in origin:
            regex_parts.append(re.escape(origin).replace(r"\*", ".*"))
        else:
            exact_origins.append(origin)
    allow_origin_regex = "|".join(regex_parts) or None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=exact_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers with prefix
    app.include_router(v1_router, prefix="/api/v1")

    logger.info("FastAPI application created")

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )
