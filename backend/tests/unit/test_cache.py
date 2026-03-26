"""Tests for TTL cache."""

import time

from src.utils.cache import TTLCache


def test_cache_set_get():
    cache = TTLCache()
    cache.set("key1", "value1", ttl_seconds=60)
    assert cache.get("key1") == "value1"


def test_cache_miss():
    cache = TTLCache()
    assert cache.get("nonexistent") is None


def test_cache_expiry():
    cache = TTLCache()
    cache.set("key1", "value1", ttl_seconds=0)
    time.sleep(0.01)
    assert cache.get("key1") is None


def test_cache_delete():
    cache = TTLCache()
    cache.set("key1", "value1", ttl_seconds=60)
    cache.delete("key1")
    assert cache.get("key1") is None


def test_cache_cleanup():
    cache = TTLCache()
    cache.set("fresh", "yes", ttl_seconds=60)
    cache.set("stale", "yes", ttl_seconds=0)
    time.sleep(0.01)
    removed = cache.cleanup()
    assert removed == 1
    assert cache.get("fresh") == "yes"


def test_cache_stats():
    cache = TTLCache()
    cache.set("a", 1, 60)
    cache.get("a")  # hit
    cache.get("b")  # miss
    stats = cache.stats
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1
