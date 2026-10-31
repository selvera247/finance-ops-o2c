"""TTL LRU cache — MVP in-process; Redis-shaped key API for Memorystore later.

Never use as source of truth for HITL decisions or payment apply.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Hashable, TypeVar

T = TypeVar("T")


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TtlLruCache:
    """Thread-safe TTL + LRU cache.

    Env:
      FINANCE_OPS_CACHE_MAX — max entries (default 512)
      FINANCE_OPS_CACHE_DISABLED — "1"/"true" disables caching
    """

    def __init__(self, max_entries: int | None = None) -> None:
        env_max = os.getenv("FINANCE_OPS_CACHE_MAX", "").strip()
        self.max_entries = max_entries or (int(env_max) if env_max.isdigit() else 512)
        self.disabled = os.getenv("FINANCE_OPS_CACHE_DISABLED", "").lower() in {
            "1",
            "true",
            "yes",
        }
        self._data: OrderedDict[Hashable, _Entry] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "backend": "memory_ttl_lru",
                "disabled": self.disabled,
                "size": len(self._data),
                "max_entries": self.max_entries,
                "hits": self.hits,
                "misses": self.misses,
            }

    def get(self, key: Hashable) -> Any | None:
        if self.disabled:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return None
            if entry.expires_at <= now:
                self._data.pop(key, None)
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return entry.value

    def set(self, key: Hashable, value: Any, ttl_seconds: float) -> None:
        if self.disabled:
            return
        expires = time.monotonic() + max(0.0, float(ttl_seconds))
        with self._lock:
            self._data[key] = _Entry(value=value, expires_at=expires)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def delete(self, key: Hashable) -> None:
        with self._lock:
            self._data.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self._data if isinstance(k, str) and k.startswith(prefix)]
            for k in keys:
                self._data.pop(k, None)
            return len(keys)

    def get_or_set(
        self,
        key: Hashable,
        ttl_seconds: float,
        factory: Callable[[], T],
    ) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        value = factory()
        self.set(key, value, ttl_seconds)
        return value


# Process-wide default (swap for Redis client with same get/set/delete API in prod)
DEFAULT_CACHE = TtlLruCache()
