"""StateCache — TTL 内存缓存。

降低快照构建频率，避免重复聚合系统状态。
默认 TTL 5 秒，线程安全（无锁 — 单线程 uvicorn）。
"""

from __future__ import annotations

import time
from typing import Any


class StateCache:
    """TTL 内存缓存。set() 时指定存活秒数，get() 时自动过期。"""

    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.monotonic() > expires:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: float = 5.0) -> None:
        self._store[key] = (time.monotonic() + ttl, value)

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    @property
    def size(self) -> int:
        return len(self._store)
