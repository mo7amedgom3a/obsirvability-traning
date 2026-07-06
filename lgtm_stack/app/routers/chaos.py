import asyncio
import random

import structlog
from fastapi import APIRouter, HTTPException

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["chaos"])

# 80% success / 10% timeout / 5% exception / 5% HTTP 500
OUTCOMES = ["success", "timeout", "exception", "http_500"]
WEIGHTS = [80, 10, 5, 5]


@router.get("/random")
async def random_outcome():
    outcome = random.choices(OUTCOMES, weights=WEIGHTS, k=1)[0]
    logger.info("random_outcome_selected", outcome=outcome)

    if outcome == "success":
        return {"status": "ok", "outcome": outcome}

    if outcome == "timeout":
        # Sleeps long enough to trip most client / gateway / load-balancer
        # timeouts (which are typically 5-10s), simulating a hung request.
        sleep_seconds = 15
        logger.warning("simulating_timeout", sleep_seconds=sleep_seconds)
        await asyncio.sleep(sleep_seconds)
        return {"status": "ok", "outcome": "timeout_but_eventually_responded"}

    if outcome == "exception":
        logger.error("simulating_unhandled_exception")
        raise ValueError("Simulated unhandled exception")

    logger.error("simulating_http_500")
    raise HTTPException(status_code=500, detail="Simulated HTTP 500 error")


@router.get("/slow")
async def slow(min_seconds: float = 0.5, max_seconds: float = 5.0):
    delay = round(random.uniform(min_seconds, max_seconds), 2)
    logger.info("slow_request_start", delay_seconds=delay)
    await asyncio.sleep(delay)
    logger.info("slow_request_end", delay_seconds=delay)
    return {"status": "ok", "delay_seconds": delay}
