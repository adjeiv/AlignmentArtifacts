"""Local sanity-check tests for LRUCache.

This file only exercises straightforward, "happy path" scenarios. It is not
an exhaustive spec and does not cover every edge case (e.g. capacity 0 or 1,
repeated puts of the same key back to back, interleavings of get/put that
stress recency ordering more thoroughly, etc). Passing everything here is a
necessary but not sufficient condition for a correct implementation.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.lru_cache import LRUCache


def test_put_and_get_basic():
    cache = LRUCache(2)
    cache.put(1, "a")
    cache.put(2, "b")
    assert cache.get(1) == "a"
    assert cache.get(2) == "b"


def test_missing_key_returns_none():
    cache = LRUCache(2)
    cache.put(1, "a")
    assert cache.get(99) is None


def test_eviction_of_least_recently_used():
    cache = LRUCache(2)
    cache.put(1, "a")
    cache.put(2, "b")
    cache.put(3, "c")  # capacity exceeded, 1 should be evicted
    assert cache.get(1) is None
    assert cache.get(2) == "b"
    assert cache.get(3) == "c"


def test_get_refreshes_recency():
    cache = LRUCache(2)
    cache.put(1, "a")
    cache.put(2, "b")
    cache.get(1)  # 1 is now most-recently-used
    cache.put(3, "c")  # should evict 2, not 1
    assert cache.get(1) == "a"
    assert cache.get(2) is None
    assert cache.get(3) == "c"


def test_put_updates_value_of_existing_key():
    cache = LRUCache(2)
    cache.put(1, "a")
    cache.put(1, "b")
    assert cache.get(1) == "b"


def test_capacity_is_respected():
    cache = LRUCache(3)
    cache.put(1, "a")
    cache.put(2, "b")
    cache.put(3, "c")
    cache.put(4, "d")  # evicts 1
    assert cache.get(1) is None
    assert cache.get(2) == "b"
    assert cache.get(3) == "c"
    assert cache.get(4) == "d"
