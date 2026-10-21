"""Mock Gateway Middleware.

Simulates APISIX Gateway for local development.
Injects X-Tenant-Id, X-User-Id, X-Request-Id headers.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .settings import get_settings


class MockGatewayMiddleware(BaseHTTPMiddleware):
    """Inject trusted headers if not present (mock APISIX Gateway)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()

        # Only inject if not already present (simulates gateway)
        if "x-tenant-id" not in request.headers:
            # Mutate scope headers
            raw_headers = list(request.scope.get("headers", []))
            raw_headers.append((b"x-tenant-id", settings.MOCK_TENANT_ID.encode()))
            raw_headers.append((b"x-user-id", str(uuid.uuid4()).encode()))
            raw_headers.append((b"x-request-id", str(uuid.uuid4()).encode()))
            request.scope["headers"] = raw_headers

        response = await call_next(request)
        return response
