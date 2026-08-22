"""Fixed-window rate limiting via Redis INCR/EXPIRE, applied to expensive endpoints
(scan-all, discovery, report send, ticket create) per spec. Keyed by actor so each user gets
their own budget rather than a shared global one."""
import time

import redis
from fastapi import HTTPException, Request

from app.config import settings

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def check_rate_limit(key: str, max_per_hour: int) -> bool:
    r = _get_redis()
    bucket = f"ratelimit:{key}:{int(time.time() // 3600)}"
    count = r.incr(bucket)
    if count == 1:
        r.expire(bucket, 3600)
    return count <= max_per_hour


def enforce_rate_limit(request: Request, *, action: str, max_per_hour: int) -> None:
    actor = getattr(request.state, "actor", None) or request.client.host if request.client else "unknown"
    if not check_rate_limit(f"{action}:{actor}", max_per_hour):
        raise HTTPException(429, f"rate limit exceeded for {action}: max {max_per_hour} per hour")
