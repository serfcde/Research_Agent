"""Main FastAPI application entry point."""

import time
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from app.config.settings import settings
from app.utils.logger import get_logger
from app.api.deps import require_api_key
from app.api.routes import limiter, router

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

    # Rate limiting (slowapi) — limits are declared on individual routes.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS restricted to configured origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Structured JSON for unhandled errors (no stack traces to clients)
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": "An unexpected error occurred."},
        )

    # Include routers (API-key protected; /api/status stays public)
    app.include_router(
        router, prefix="/api", tags=["research"], dependencies=[Depends(require_api_key)]
    )

    # Health check endpoint (public; used by Docker/deploy healthchecks)
    @app.get("/health", tags=["system"])
    async def health_check():
        """Health check: process is up and, when configured, the DB answers."""
        from app.services.run_store import PostgresRunStore, get_run_store

        health = {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "timestamp": time.time(),
        }
        store = get_run_store()
        if isinstance(store, PostgresRunStore):
            db_ok = await store.ping()
            health["database"] = "ok" if db_ok else "unreachable"
            if not db_ok:
                health["status"] = "degraded"
                return JSONResponse(status_code=503, content=health)
        return health

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
