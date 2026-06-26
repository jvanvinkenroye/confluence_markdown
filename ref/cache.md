# Cache reference

`src/confluence_markdown/cache.py`

## Defaults

| Constant | Value | Notes |
|----------|-------|-------|
| `DEFAULT_CACHE_DIR` | `~/.cache/confluence-markdown/` | File storage |
| `DEFAULT_TTL` | 3600 s | 1 hour |
| `DEFAULT_MAX_ENTRIES` | 500 | LRU eviction limit |

## Cache(…) constructor

```python
Cache(
    cache_dir: Path | None = None,
    ttl: int = 3600,
    enabled: bool = True,
    max_entries: int = 500,
)
```

## Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `get(key)` | `Any \| None` | Returns `None` if missing or expired |
| `set(key, value)` | `None` | Writes JSON; evicts oldest if over limit |
| `delete(key)` | `None` | Remove single entry |
| `clear()` | `int` | Delete all entries; return count |
| `cleanup_expired()` | `int` | Remove TTL-expired entries; return count |

## Storage format

Each entry is an MD5-hashed `.json` file:

```json
{
  "timestamp": 1718000000.0,
  "key": "<first 100 chars of original key>",
  "value": "<any JSON-serializable value>"
}
```

## Eviction

`_evict_if_needed()` is called after every `set()`. It sorts all `.json` files by `mtime` and removes the oldest ones until `len <= max_entries`.

## CLI flags

| Flag | Effect |
|------|--------|
| `--no-cache` | `Cache(enabled=False)` — all gets return `None`, sets are no-ops |
| `--clear-cache` | Call `cache.clear()` and exit |
