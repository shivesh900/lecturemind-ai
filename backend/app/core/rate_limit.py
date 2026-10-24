"""Small in-memory sliding-window rate limiter.

Good for a single API process. For several replicas, swap the store for Redis
(the interface is just `hit(key) -> bool`).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_s: float = 60.0) -> tuple[bool, float]:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False, window_s - (now - q[0])
        q.append(now)
        return True, 0.0

    def check(self, key: str, limit: int, window_s: float = 60.0) -> None:
        ok, retry = self.hit(key, limit, window_s)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {int(retry) + 1}s.",
                headers={"Retry-After": str(int(retry) + 1)},
            )

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter()
