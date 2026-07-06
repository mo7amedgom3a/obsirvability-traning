import asyncio
import time

import structlog
from fastapi import APIRouter, Query

from app.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["resource"])

# Module-level list -> intentional "leak": nothing ever evicts these unless
# /memory-leak/reset is called. Restart the process (or let your orchestrator's
# memory limit kill it) to see it return to baseline.
_memory_leak_store: list[bytes] = []


def _burn_cpu_sync(duration_seconds: float) -> int:
    """Busy-loop that pegs a CPU core for the given duration.

    This is intentionally synchronous/blocking, the same way a poorly written
    handler (e.g. doing heavy sync computation in an async def route) would
    behave in production: it starves the event loop and every other
    concurrent request on this worker stalls until it's done.
    """
    end_time = time.perf_counter() + duration_seconds
    iterations = 0
    while time.perf_counter() < end_time:
        iterations += 1
        _ = (iterations * iterations) % 7919
    return iterations


@router.get("/cpu-burn")
async def cpu_burn(
    duration_seconds: float = Query(5.0, ge=0.1, le=settings.cpu_burn_max_seconds),
    blocking: bool = Query(
        True,
        description=(
            "true (default): burn CPU directly on the event loop thread, "
            "starving all other requests (worst case, very realistic bug). "
            "false: offload to a thread pool executor, still burns a CPU "
            "core but keeps the event loop responsive."
        ),
    ),
):
    logger.warning("cpu_burn_start", duration_seconds=duration_seconds, blocking=blocking)
    start = time.perf_counter()

    if blocking:
        iterations = _burn_cpu_sync(duration_seconds)
    else:
        loop = asyncio.get_running_loop()
        iterations = await loop.run_in_executor(None, _burn_cpu_sync, duration_seconds)

    elapsed = round(time.perf_counter() - start, 2)
    logger.warning("cpu_burn_end", elapsed_seconds=elapsed, iterations=iterations)
    return {
        "status": "ok",
        "elapsed_seconds": elapsed,
        "iterations": iterations,
        "blocking": blocking,
    }


@router.get("/memory-leak")
async def memory_leak(
    size_mb: int = Query(10, ge=1, le=settings.memory_leak_max_mb_per_call)
):
    chunk = bytes(size_mb * 1024 * 1024)
    _memory_leak_store.append(chunk)
    total_mb = sum(len(c) for c in _memory_leak_store) / (1024 * 1024)

    logger.warning(
        "memory_leak_grew",
        chunk_mb=size_mb,
        total_leaked_mb=round(total_mb, 2),
        chunks_held=len(_memory_leak_store),
    )
    return {
        "status": "ok",
        "chunk_mb": size_mb,
        "total_leaked_mb": round(total_mb, 2),
        "chunks_held": len(_memory_leak_store),
    }


@router.get("/memory-leak/status")
async def memory_leak_status():
    total_mb = sum(len(c) for c in _memory_leak_store) / (1024 * 1024)
    return {"total_leaked_mb": round(total_mb, 2), "chunks_held": len(_memory_leak_store)}


@router.post("/memory-leak/reset")
async def memory_leak_reset():
    freed_mb = sum(len(c) for c in _memory_leak_store) / (1024 * 1024)
    _memory_leak_store.clear()
    logger.info("memory_leak_reset", freed_mb=round(freed_mb, 2))
    return {"status": "ok", "freed_mb": round(freed_mb, 2)}
