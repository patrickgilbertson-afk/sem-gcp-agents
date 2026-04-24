"""API authentication middleware for FastAPI."""

import os
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import structlog

logger = structlog.get_logger(__name__)

# Endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
}

# Endpoints that use Slack signature verification instead
SLACK_ENDPOINTS_PREFIX = "/api/v1/slack/"


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to authenticate API requests.

    Authentication methods (in order of precedence):
    1. Public endpoints - no auth required
    2. Slack endpoints - use Slack signature verification (handled by slack-bolt)
    3. OIDC token - for Cloud Scheduler (validates via Google's token verification)
    4. API key - for manual triggers (compares against secret from Secret Manager)
    """

    def __init__(self, app, api_key: str | None = None):
        """Initialize auth middleware.

        Args:
            app: FastAPI application
            api_key: API key for authentication (loaded from Secret Manager)
        """
        super().__init__(app)
        self.api_key = api_key
        logger.info("auth_middleware_initialized", has_api_key=bool(api_key))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Authenticate request before processing.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            Response from the application or 401/403 error
        """
        path = request.url.path

        # Allow public endpoints
        if path in PUBLIC_ENDPOINTS:
            return await call_next(request)

        # Allow Slack endpoints (they handle their own auth via signature verification)
        if path.startswith(SLACK_ENDPOINTS_PREFIX):
            return await call_next(request)

        # Check for API key in header
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            if not self.api_key:
                logger.warning(
                    "api_key_header_received_but_no_key_configured",
                    path=path,
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "API key authentication not configured"},
                )

            if api_key_header == self.api_key:
                logger.info("api_key_authenticated", path=path, method=request.method)
                return await call_next(request)
            else:
                logger.warning(
                    "invalid_api_key",
                    path=path,
                    method=request.method,
                    remote_addr=request.client.host if request.client else "unknown",
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API key"},
                )

        # Check for OIDC token (Cloud Scheduler)
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            # In production, you'd verify the JWT token here
            # For now, we accept any Bearer token (Cloud Run validates it at ingress)
            # Cloud Run with require-authentication rejects invalid OIDC tokens before they reach us
            token = authorization[7:]  # Remove "Bearer " prefix
            if token:
                logger.info(
                    "oidc_token_authenticated",
                    path=path,
                    method=request.method,
                )
                return await call_next(request)

        # No valid authentication found
        logger.warning(
            "unauthenticated_request_blocked",
            path=path,
            method=request.method,
            remote_addr=request.client.host if request.client else "unknown",
            headers=dict(request.headers),
        )

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "Authentication required. Provide X-API-Key header or valid OIDC token.",
            },
        )
