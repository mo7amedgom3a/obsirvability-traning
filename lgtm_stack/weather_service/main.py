"""
A tiny, deliberately unreliable "third-party" weather API.

Run this as a separate service. Your main chaos-service's /external-api
endpoint depends on it, so you can practice handling (and observing) a flaky
upstream dependency: random 500s, a hang that trips your client's timeout,
and 429 rate-limiting.
"""

import asyncio
import random
import sys

import structlog
from fastapi import FastAPI, Response

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(sys.stdout),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger("weather-service")

app = FastAPI(title="fake-weather-api")

OUTCOMES = ["success", "http_500", "timeout", "rate_limited"]
WEIGHTS = [70, 15, 10, 5]


@app.get("/weather")
async def get_weather(response: Response):
    outcome = random.choices(OUTCOMES, weights=WEIGHTS, k=1)[0]
    logger.info("weather_request", outcome=outcome)

    if outcome == "success":
        return {
            "city": "Cairo",
            "temperature_c": round(random.uniform(18, 40), 1),
            "condition": random.choice(["sunny", "cloudy", "windy", "rainy"]),
        }

    if outcome == "http_500":
        response.status_code = 500
        return {"error": "internal server error"}

    if outcome == "timeout":
        # Sleeps well past any sane client timeout, simulating a hung upstream.
        await asyncio.sleep(10)
        return {"error": "should not be seen by the caller"}

    response.status_code = 429
    response.headers["Retry-After"] = "2"
    return {"error": "rate limited"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
