import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.logging_config import setup_logging
from app.middleware import RequestContextMiddleware
from app.routers import basic, chaos, database, external, health, resource

setup_logging(json_logs=settings.json_logs, log_level=settings.log_level)
logger = structlog.get_logger(__name__)

app = FastAPI(
    title=settings.service_name,
    description="Chaos-engineering / observability simulation service",
    version="1.0.0",
)

app.add_middleware(RequestContextMiddleware)

app.include_router(basic.router)
app.include_router(chaos.router)
app.include_router(resource.router)
app.include_router(database.router)
app.include_router(external.router)
app.include_router(health.router)

# Exposes /metrics in Prometheus format: request count, latency histograms,
# in-progress requests, etc. -- broken down by path/method/status.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500, content={"status": "error", "detail": "Internal server error"}
    )


@app.on_event("startup")
async def on_startup():
    logger.info(
        "service_starting",
        service=settings.service_name,
        environment=settings.environment,
    )


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("service_stopping", service=settings.service_name)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.service_name,
        "docs": "/docs",
        "metrics": "/metrics",
    }
