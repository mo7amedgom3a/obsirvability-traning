import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["health"])

# Flip this (e.g. via an admin endpoint, or during a simulated slow-start)
# to see readiness probes fail while liveness stays green.
_ready = True


@router.get("/health")
async def health():
    """Generic health check, useful for uptime monitors / smoke tests."""
    return {"status": "healthy"}


@router.get("/live")
async def live():
    """Liveness: is the process up and not deadlocked? If this fails,
    Kubernetes will restart the pod."""
    return {"status": "alive"}


@router.get("/ready")
async def ready():
    """Readiness: is it safe to route traffic here right now? If this fails,
    Kubernetes removes the pod from the service's endpoints (no restart)."""
    if not _ready:
        logger.warning("readiness_check_failed")
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
