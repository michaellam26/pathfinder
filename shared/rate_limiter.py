"""Shared async rate limiter (token-bucket style)."""
import asyncio
import time


class _RateLimiter:
    """Ensures at most `rpm` calls per minute by enforcing a minimum interval."""
    def __init__(self, rpm: int):
        self._interval = 60.0 / rpm
        self._lock     = asyncio.Lock()
        self._last     = 0.0

    async def acquire(self):
        async with self._lock:
            now  = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
