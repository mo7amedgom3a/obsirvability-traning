import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger("http.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    - Assigns/propagates a request id (X-Request-ID) so a single request can be
      traced across logs, and eventually across services.
    - Binds request-scoped context (request id, method, path, client ip) so every
      log line emitted anywhere during the request automatically includes it.
    - Emits a structured "access log" line per request with status code and
      latency, the single most useful signal for building dashboards/alerts.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        logger.info("request_started")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception("request_failed_unhandled", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        log = logger.warning if response.status_code >= 500 else logger.info
        log(
            "request_finished",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
