# Exception hierarchy

`src/confluence_markdown/exceptions.py`

```
ConfluenceError (base)
├── AuthenticationError     — 401/403 or bad credentials
├── ConfigurationError      — missing/invalid config or CLI args
├── PageNotFoundError       — page URL resolved to no page
├── APIError(status_code)   — non-2xx API response
├── ContentParseError       — HTML/markdown parse failure
└── EditorError             — external editor failed
```

All exceptions are subclasses of `ConfluenceError`, so callers can catch either the base or a specific subclass.

`APIError` carries `status_code: int | None` for HTTP status inspection.
