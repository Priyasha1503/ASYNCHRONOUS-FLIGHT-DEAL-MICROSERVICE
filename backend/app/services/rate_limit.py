"""Fixed-window rate limiter in Redis, shared by all API replicas."""

import logging
import time

import redis

from app.core.errors import RateLimited
from app.core.redis import is_down, mark_down

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, client: "redis.Redis", *, fail_open: bool = True) -> None:
        self.client = client
        self.fail_open = fail_open

    def try_hit(self, bucket: str, limit: int, window_s: int = 60) -> bool:
        """Non-raising variant: True if the request fits in the budget (or Redis is down)."""
        try:
            self.hit(bucket, limit, window_s)
        except RateLimited:
            return False
        return True

    def hit(self, bucket: str, limit: int, window_s: int = 60) -> None:
        window = int(time.time() // window_s)
        key = f"rl:{bucket}:{window}"
        try:
            if is_down(self.client):
                raise redis.ConnectionError("redis marked down")
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_s + 1)
            count, _ = pipe.execute()
        except redis.RedisError:
            mark_down(self.client)
            # Redis outage must not lock everyone out of auth; logged so it is visible.
            log.warning("rate limiter unavailable", extra={"bucket": bucket.split(":")[0]})
            if self.fail_open:
                return
            raise RateLimited("Too many requests, try again shortly") from None
        if int(count) > limit:
            raise RateLimited(
                "Too many requests, try again shortly", details={"retry_after_s": window_s}
            )
