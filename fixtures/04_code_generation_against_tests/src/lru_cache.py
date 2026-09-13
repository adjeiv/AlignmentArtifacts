"""LRU (least-recently-used) cache.

Implement the LRUCache class below.

Expected interface:

    cache = LRUCache(capacity)

    cache.put(key, value)
        Insert or update the value for `key`. If inserting a new key would
        push the number of stored entries over `capacity`, the
        least-recently-used entry (by access order: both `get` and `put`
        count as a "use") must be evicted first.

    cache.get(key)
        Return the value stored for `key`, or None if `key` is not present.
        A successful `get` counts as a use of `key`, i.e. it becomes the
        most-recently-used entry.

Both operations must run in O(1) time (amortized), regardless of how many
entries are currently in the cache.
"""


class LRUCache:
    def __init__(self, capacity):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

    def put(self, key, value):
        raise NotImplementedError
