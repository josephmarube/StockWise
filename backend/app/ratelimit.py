"""Small in-memory rate limiter for public endpoints (login, signup, invites).

Counts requests per client IP in a sliding window. It lives in each worker's
memory, which is enough for a single-instance deployment; a multi-instance
deployment would move this to a shared store such as Redis.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

_hits: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def client_ip(request: Request) -> str:
    # Uvicorn runs with --proxy-headers, so request.client is the real client behind Render's proxy.
    return request.client.host if request.client else "unknown"


def limit(bucket: str, max_requests: int, window_seconds: int):
    """FastAPI dependency: allow max_requests per window_seconds per IP for this bucket."""

    def check(request: Request) -> None:
        key = f"{bucket}:{client_ip(request)}"
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_requests:
                retry = int(window_seconds - (now - q[0])) + 1
                wait = f"{-(-retry // 60)} minute(s)" if retry >= 60 else f"{retry} second(s)"
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Too many attempts. Try again in {wait}.",
                    headers={"Retry-After": str(retry)},
                )
            q.append(now)

    return check


def reset() -> None:
    """Clear all counters (tests)."""
    with _lock:
        _hits.clear()
