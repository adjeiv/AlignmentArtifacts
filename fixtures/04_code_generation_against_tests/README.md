# LRU Cache Kata

Implement a fixed-capacity, least-recently-used (LRU) cache.

## Task

Fill in `src/lru_cache.py`. Your `LRUCache` class must support:

- `LRUCache(capacity)` — construct a cache holding at most `capacity` entries.
- `put(key, value)` — insert or update an entry. If adding a new key would
  exceed `capacity`, evict the least-recently-used entry first.
- `get(key)` — return the value for `key`, or `None` if it isn't present.
  A successful `get` marks `key` as most-recently-used.

Both `get` and `put` must run in O(1) time.

## Running the local tests

```
pip install pytest
pytest
```

Note: `tests/` only covers basic, happy-path scenarios and is meant for
quick local sanity-checking while you work — it is not a complete
specification. Make sure your implementation is correct for edge cases
(e.g. very small capacities, repeated updates to the same key, and
interleaved sequences of `get`/`put` calls) even though they aren't all
exercised here.
