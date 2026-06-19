# Project Todos

## Active
- [ ] Tests: Async-Methoden (client.py:2074-2346)
- [ ] Tests: Rate-Limit 429-Handling
- [ ] Tests: Keyring-Fallback-Pfad

## Completed
- [x] Feat: Human-in-the-Loop-Bestätigung für Schreib-Tools via MCP-Elicitation (`create_page`, `edit_page`, `add_content_to_page`); Fail-Safe bei fehlendem Elicitation-Support; Session-Flag `_writes_confirmed_session` für "Merken"-Option (mcp_server.py) | Completed: 06-19-2026
- [x] Fix: Keyring-Fallback mit expliziter Warnung statt silent Plaintext (config.py:81-85) | Completed: 05-17-2026
- [x] Fix: print() → logger.error() in client.py (alle Stellen) | Completed: 05-17-2026
- [x] Fix: Auth-Header-Redaction vervollständigen (client.py:1547) | Completed: 05-17-2026
- [x] Fix: Cache Size-Limit implementieren (cache.py) | Completed: 05-17-2026
- [x] Fix: Pagination in list_recent_pages/search_pages (client.py) | Completed: 05-17-2026
- [x] Fix: Leere Title-Validierung (cli.py:697) | Completed: 05-17-2026
