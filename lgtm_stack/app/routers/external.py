import httpx
import structlog
from fastapi import APIRouter, HTTPException

from app.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["external"])


@router.get("/external-api")
async def external_api():
    """
    Calls the fake weather service (see weather_service/) which randomly
    returns success / 500 / a hang (-> client timeout) / 429. This mirrors
    depending on a flaky third-party API and shows how to translate upstream
    failure modes into sane status codes + structured logs for your own
    service.
    """
    url = f"{settings.weather_api_url}/weather"
    logger.info("external_call_start", target=url)

    try:
        async with httpx.AsyncClient(timeout=settings.weather_api_timeout_seconds) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        logger.error(
            "external_call_timeout",
            target=url,
            timeout_seconds=settings.weather_api_timeout_seconds,
        )
        raise HTTPException(status_code=504, detail="Upstream weather service timed out")
    except httpx.ConnectError:
        logger.error("external_call_connect_error", target=url)
        raise HTTPException(status_code=502, detail="Could not reach weather service")

    if response.status_code == 429:
        logger.warning("external_call_rate_limited", target=url)
        raise HTTPException(status_code=429, detail="Weather service rate-limited us")

    if response.status_code >= 500:
        logger.error(
            "external_call_upstream_error", target=url, upstream_status=response.status_code
        )
        raise HTTPException(status_code=502, detail="Weather service returned an error")

    data = response.json()
    logger.info("external_call_success", target=url, upstream_status=response.status_code)
    return {"status": "ok", "weather": data}
