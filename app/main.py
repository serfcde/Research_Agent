"""Main FastAPI application entry point."""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.utils.logger import get_logger
from app.api.routes import router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for app startup/shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.log_level}")

    missing = [
        name
        for name, value in (
            ("GROQ_API_KEY", settings.groq_api_key),
            ("TAVILY_API_KEY", settings.tavily_api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in your API keys."
        )

    from app.services.run_store import get_run_store
    from app.services.orchestration import get_orchestrator

    await get_run_store().init()

    # Crash recovery: resume any runs a previous process left in-flight
    # (they continue from their last LangGraph checkpoint).
    resumed = await get_orchestrator().resume_interrupted_runs()
    if resumed:
        logger.info(f"Scheduled {resumed} interrupted run(s) for resumption")

    yield

    # Shutdown
    from app.graph.graph import aclose_graph

    await get_run_store().close()
    await aclose_graph()
    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-level agentic research system with multi-agent orchestration",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(router, prefix="/api", tags=["research"])

    # Health check endpoint
    @app.get("/health", tags=["system"])
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "timestamp": time.time(),
        }

    # Root endpoint
    @app.get("/", tags=["system"])
    async def root():
        """Root endpoint with API info."""
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs_url": "/docs",
            "openapi_url": "/openapi.json",
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
