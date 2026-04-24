"""FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    logger.info(
        "application_starting",
        environment=settings.environment,
        dry_run=settings.dry_run,
    )
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title="SEM GCP Agents",
    description="AI-powered SEM campaign management agents",
    version="0.1.0",
    lifespan=lifespan,
)

# Add authentication middleware
from src.api.middleware import AuthMiddleware

app.add_middleware(AuthMiddleware, api_key=settings.api_auth_key)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "dry_run": settings.dry_run,
        "kill_switch": settings.kill_switch_enabled,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "SEM GCP Agents",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# Import and include routers
from src.api import orchestrator, agents, slack, approvals, reports

app.include_router(orchestrator.router, prefix="/api/v1/orchestrator", tags=["orchestrator"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(slack.router, prefix="/api/v1/slack", tags=["slack"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["approvals"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
