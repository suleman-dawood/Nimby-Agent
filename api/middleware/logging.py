"""Request logging middleware — logs method, path, status, duration for every API call."""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s → %d (%.0fms)",
                method, path, response.status_code, duration_ms,
            )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "%s %s → FAILED (%.0fms): %s",
                method, path, duration_ms, str(exc)[:200],
            )
            raise
