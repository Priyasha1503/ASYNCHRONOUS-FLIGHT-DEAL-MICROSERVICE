"""Explicit price-change simulation for the demo provider (development and demos only).

Demo fares are deterministic, so a monitored demo route would never move and alerts could never be
seen working. Instead of inventing drift, a user can *explicitly* apply a percentage change to a
demo query; the demo provider multiplies its prices by the stored factor. The factor is cumulative,
bounded, expires after a week, and is only reachable when `settings.demo_simulation_enabled`.
"""

from decimal import Decimal, InvalidOperation

import redis

from app.core.redis import is_down, mark_down

PREFIX = "demo:adjust:"
TTL_S = 7 * 24 * 3600
MIN_FACTOR, MAX_FACTOR = Decimal("0.2"), Decimal("3")


def read_adjustment(client: "redis.Redis", query_key: str) -> Decimal | None:
    if is_down(client):
        return None
    try:
        raw = client.get(PREFIX + query_key)
    except redis.RedisError:
        mark_down(client)
        return None
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def apply_price_change(client: "redis.Redis", query_keys: list[str], percent: Decimal) -> Decimal:
    """Multiply the current factor by (1 + percent/100) for every upstream key; returns the new
    factor of the first key."""
    first: Decimal | None = None
    for key in query_keys:
        current = read_adjustment(client, key) or Decimal(1)
        factor = min(MAX_FACTOR, max(MIN_FACTOR, current * (1 + percent / 100)))
        factor = factor.quantize(Decimal("0.0001"))
        client.set(PREFIX + key, str(factor), ex=TTL_S)
        first = first if first is not None else factor
    return first or Decimal(1)
