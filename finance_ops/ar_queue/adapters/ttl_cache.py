"""Cache adapter — wraps process TTL LRU with AR key helpers."""

from __future__ import annotations

from typing import Any

from finance_ops.runtime.cache import DEFAULT_CACHE, TtlLruCache

METRICS_TTL = 15.0
LIST_TTL = 10.0
MATCH_TTL = 60.0


class TtlCacheAdapter:
    def __init__(self, cache: TtlLruCache | None = None) -> None:
        self._cache = cache or DEFAULT_CACHE

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._cache.set(key, value, ttl_seconds)

    def invalidate_prefix(self, prefix: str) -> int:
        return self._cache.invalidate_prefix(prefix)

    def stats(self) -> dict[str, Any]:
        return self._cache.stats()

    def invalidate_queue(self) -> None:
        self.invalidate_prefix("ar:")


DEFAULT_QUEUE_CACHE = TtlCacheAdapter()
