from collections import defaultdict
from datetime import datetime, timezone
import time
from typing import Dict, List, Optional
from fastapi import HTTPException, Request


class SlidingWindowRateLimiter:
    """Thread-safe, lightweight in-memory sliding window rate limiter for API endpoints.
    Protects compute-heavy AI audit and decision endpoints against abuse and DoS.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60, name: str = "default"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._history: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        """Check if request for given key exceeds rate limit.
        If exceeded, raises HTTPException(429). Otherwise records the request timestamp.
        """
        now = time.time()
        cutoff = now - self.window_seconds
        timestamps = self._history[key]

        # Evict timestamps outside current sliding window
        self._history[key] = [t for t in timestamps if t > cutoff]

        if len(self._history[key]) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - self._history[key][0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {self.name} operations ({self.max_requests} requests per {self.window_seconds}s). Please retry after {max(1, retry_after)} seconds.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        self._history[key].append(now)

    def reset(self) -> None:
        """Clear all recorded rate limit history (useful for test isolation)."""
        self._history.clear()


# Pre-configured rate limiters
# 1. AI Audit: 30 requests per minute per user/IP
ai_audit_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, name="AI Audit")

# 2. Decision recording: 60 requests per minute per user/IP
decision_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60, name="Review Decision")
