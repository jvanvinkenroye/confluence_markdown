# Project Todos

## Active

## Completed
- [x] Release v0.3.1: Umlaut-Fix für Attachment-Kommentare (e66b389) nach PyPI veröffentlicht | Completed: 07-13-2026
- [x] Tests: Async-Methoden (test_async_client.py) | Completed: 07-13-2026
- [x] Tests: Rate-Limit 429-Handling (test_rate_limit.py) | Completed: 07-13-2026
- [x] Tests: Keyring-Fallback-Pfad (test_keyring_fallback.py) | Completed: 07-13-2026
- [x] Feat: Confluence storage format (XHTML) mode — lossless round-trips for tables/macros without Markdown conversion. MCP: `*_storage` tools (preferred for agents) + `*_md` tools (renamed); CLI `--format md|storage`; `_validate_storage_xhtml` + `_prettify_storage` helpers; bug fix for `content_type="html"` in `edit_page_with_editor`. **BREAKING:** MCP tools `get_page`/`edit_page`/`create_page`/`add_content_to_page` renamed to `*_md` suffix. | Completed: 06-22-2026
- [x] Feat: Human-in-the-Loop-Bestätigung für Schreib-Tools via MCP-Elicitation (`create_page`, `edit_page`, `add_content_to_page`); Fail-Safe bei fehlendem Elicitation-Support; Session-Flag `_writes_confirmed_session` für "Merken"-Option (mcp_server.py) | Completed: 06-19-2026
- [x] Fix: Keyring-Fallback mit expliziter Warnung statt silent Plaintext (config.py:81-85) | Completed: 05-17-2026
- [x] Fix: print() → logger.error() in client.py (alle Stellen) | Completed: 05-17-2026
- [x] Fix: Auth-Header-Redaction vervollständigen (client.py:1547) | Completed: 05-17-2026
- [x] Fix: Cache Size-Limit implementieren (cache.py) | Completed: 05-17-2026
- [x] Fix: Pagination in list_recent_pages/search_pages (client.py) | Completed: 05-17-2026
- [x] Fix: Leere Title-Validierung (cli.py:697) | Completed: 05-17-2026
