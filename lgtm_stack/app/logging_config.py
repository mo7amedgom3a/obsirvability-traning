"""
Structured logging configuration.

Best practices applied here:
- Logs are emitted as single-line JSON (easy to ingest into ELK / Loki / CloudWatch / Datadog).
- Every log line carries a timestamp, level, logger name, and event name.
- Request-scoped fields (request_id, http_method, http_path, ...) are bound via
  contextvars so every log line emitted while handling a request is automatically
  tagged, without having to pass `request_id` around manually.
- uvicorn's own loggers are routed through the same JSON formatter, so access
  logs and app logs look consistent in your log aggregator.
- Exceptions are rendered with full tracebacks as structured fields, not just
  dumped as unstructured text.
"""

import logging
import sys

import structlog


def setup_logging(json_logs: bool = True, log_level: str = "INFO") -> None:
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Route uvicorn's own loggers through the same JSON formatter instead of
    # letting them print their default unstructured lines.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = [handler]
        uv_logger.propagate = False

    # Quiet noisy third-party loggers unless we're debugging.
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("httpcore").setLevel("WARNING")
