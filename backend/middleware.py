"""
Request logging and timing middleware.

Logs every request with method, path, status code, and latency (ms).
Adds X-Response-Time header to every response for client-side monitoring.
"""
import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("voting.access")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Measures end-to-end latency of every HTTP request and:
      - Logs at INFO level: method, path, status, latency, client IP
      - Adds X-Response-Time response header (ms, 1 dp)
      - Logs WARNING for any request exceeding 1 000 ms
    """

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1_000
            logger.error(
                "UNHANDLED method=%s path=%s latency_ms=%.1f",
                request.method,
                request.url.path,
                latency_ms,
            )
            raise

        latency_ms = (time.perf_counter() - start) * 1_000
        level = logging.WARNING if latency_ms > 1_000 else logging.INFO
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        logger.log(
            level,
            "%-6s %-40s %d  %.1f ms  ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            client_ip,
        )
        response.headers["X-Response-Time"] = f"{latency_ms:.1f}ms"
        return response
