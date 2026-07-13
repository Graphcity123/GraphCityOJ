from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS


class RateLimiter:
    """Simple in-memory rate limiter: max N requests per window_seconds per user."""

    def __init__(self, max_requests: int = 3, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._records: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        records = self._records[user_id]
        # Prune old entries
        self._records[user_id] = [t for t in records if t > cutoff]
        if len(self._records[user_id]) >= self.max_requests:
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )
        self._records[user_id].append(now)


# Global instance used by all route handlers
judge_rate_limiter = RateLimiter(max_requests=3, window_seconds=60)
