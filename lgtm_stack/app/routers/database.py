import asyncio
import random
import time

import structlog
from fastapi import APIRouter

from app.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["database"])


async def _fake_query(query: str) -> dict:
    """
    Simulates a DB call. `slow_db_probability` of the time it takes
    `slow_db_sleep_seconds` (default 4s) to "return", the rest of the time
    it's fast. Logged as a span-style structured event so you can pull
    p50/p95/p99 duration_ms straight out of your log/metrics backend.
    """
    is_slow = random.random() < settings.slow_db_probability
    sleep_seconds = (
        settings.slow_db_sleep_seconds if is_slow else round(random.uniform(0.01, 0.15), 3)
    )

    start = time.perf_counter()
    await asyncio.sleep(sleep_seconds)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    logger.info(
        "db_query_span",
        span_name="db.query",
        db_system="fake-postgres",
        query=query,
        is_slow=is_slow,
        duration_ms=duration_ms,
    )
    return {"rows": random.randint(0, 50), "duration_ms": duration_ms, "is_slow": is_slow}


@router.get("/db")
async def db_endpoint():
    result = await _fake_query("SELECT * FROM orders WHERE status = 'pending'")
    logger.info("db_endpoint_completed", **result)
    return {"status": "ok", **result}
