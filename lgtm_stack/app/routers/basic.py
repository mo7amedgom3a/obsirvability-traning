import structlog
from fastapi import APIRouter, HTTPException

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["basic"])


@router.get("/success")
async def success():
    logger.info("success_endpoint_called")
    return {"status": "ok", "message": "This request always succeeds"}


@router.get("/error")
async def error():
    logger.error("error_endpoint_called", reason="forced_error")
    raise HTTPException(status_code=500, detail="Simulated internal server error")
