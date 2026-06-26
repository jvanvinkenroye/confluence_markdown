# Architecture

## Package layout

```
src/confluence_markdown/
├── __init__.py       # version string
├── main.py           # entrypoint → cli.main()
├── cli.py            # argument parsing, action dispatch, interactive UI
├── client.py         # ConfluenceClient — all API + content logic
├── config.py         # ConfigManager — profiles, keychain, file I/O
├── cache.py          # Cache — file-based TTL cache with LRU eviction
└── exceptions.py     # exception hierarchy
```

## Dependency graph

```
main.py
  └── cli.py
        ├── client.py
        │     ├── cache.py
        │     ├── requests (sync HTTP)
        │     ├── httpx (async HTTP)
        │     ├── markdownify / bs4 / markdown (HTML↔Markdown)
        │     └── tenacity (retry/backoff)
        └── config.py
              └── keyring (macOS Keychain / SecretService)
```

## Auth flow

1. `cli.load_credentials()` — merge CLI flags → config file → prompt
2. `ConfluenceClient.__init__()` builds `requests.Session` with headers:
   - Token + username → `Basic <base64(user:token)>`
   - Token only → `Bearer <token>`
   - Username + password → `Basic <base64(user:password)>`
3. Async operations (`httpx`) copy the same headers from `_async_headers`.

## Config persistence

- File: `~/.config/confluence-markdown/config.json` (permissions 600)
- Secrets: stored in system keychain under service `"confluence-markdown"`, account `"<profile>:<field>"`
- Flag `token_in_keychain: true` / `password_in_keychain: true` in JSON marks that the value must be resolved from keychain at load time.

## Cache persistence

- Directory: `~/.cache/confluence-markdown/`
- Each entry: MD5-hashed filename, JSON with `{timestamp, key, value}`
- TTL: 3600 s (1 hour); max entries: 500 (LRU eviction by mtime)

## Async pattern

Long-running batch operations use `asyncio` + `httpx`:
- `async_get_pages_batch()` — parallel page fetches
- `async_download_pages_batch()` — parallel markdown downloads
- `async_list_children_recursive()` — recursive child enumeration
- Sync wrappers `download_pages_parallel()` / `list_children_recursive_parallel()` call `asyncio.run()`.

## Action dispatch (cli.py:main)

```
parse args
  → early-exit gates (--list-profiles, --clear-cache, config show/list/set/delete)
  → load_credentials()
  → validate_auth()
  → create_client()
  → ACTION_HANDLERS[action](client, args)   # or special-case for config/test-auth
```
