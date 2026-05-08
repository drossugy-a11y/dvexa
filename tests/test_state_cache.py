"""Tests for StateCache — TTL 内存缓存"""

from __future__ import annotations

import time

from surface.state_cache import StateCache


class TestStateCache:
    def setup_method(self):
        self.cache = StateCache()

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_missing(self):
        assert self.cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        self.cache.set("key2", "value2", ttl=0.1)
        assert self.cache.get("key2") == "value2"
        time.sleep(0.15)
        assert self.cache.get("key2") is None

    def test_invalidate_single_key(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.invalidate("a")
        assert self.cache.get("a") is None
        assert self.cache.get("b") == 2

    def test_invalidate_all(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.invalidate()
        assert self.cache.get("a") is None
        assert self.cache.get("b") is None

    def test_size(self):
        assert self.cache.size == 0
        self.cache.set("a", 1)
        assert self.cache.size == 1
        self.cache.set("b", 2)
        assert self.cache.size == 2
        self.cache.invalidate("a")
        assert self.cache.size == 1

    def test_overwrite_extends_ttl(self):
        self.cache.set("k", "old", ttl=0.05)
        time.sleep(0.03)
        self.cache.set("k", "new", ttl=5.0)
        assert self.cache.get("k") == "new"

    def test_expired_entry_not_counted_in_size(self):
        self.cache.set("k", "v", ttl=0.05)
        time.sleep(0.1)
        # get() 清除过期条目
        self.cache.get("k")
        assert self.cache.size == 0
