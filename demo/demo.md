# confluence-markdown — Demo

*2026-07-14T21:14:43Z by Showboat 0.6.1*
<!-- showboat-id: 372da57d-f329-4bd0-8565-617fcd27b08e -->

confluence-markdown ist ein CLI-Tool und MCP-Server, um Confluence-Data-Center-Seiten als Markdown zu lesen, zu bearbeiten und zu organisieren. Diese Demo zeigt die wichtigsten Funktionen gegen eine echte Confluence-Instanz (wisman.izus.uni-stuttgart.de). Die Zugangsdaten kommen aus einem gespeicherten Profil (macOS-Schlüsselbund), es steht kein Secret in diesem Dokument.

## Installation und Version — das Paket kommt von PyPI und bringt zwei Entry-Points mit: `confluence-markdown` (CLI) und `confluence-markdown-mcp` (MCP-Server).

```bash
uv run confluence-markdown --version
```

```output
confluence-markdown 0.3.1
```

## Authentifizierung — Zugangsdaten liegen in einem Config-Profil, Secrets im System-Schlüsselbund. `test-auth` prüft sie gegen die Instanz:

```bash
uv run confluence-markdown --action test-auth --config
```

```output
INFO: Loading config from profile: default
INFO: Testing authentication...
INFO: Authentication successful!
   User: Jan Vanvinkenroye
   Username: ac118465
   User Key: ff808181562ce98301567893e5f50013
```

## Seite als Markdown lesen — `read` holt eine Seite und konvertiert das Confluence-XHTML nach Markdown (`--raw` gibt reines Markdown ohne Rich-Rendering aus):

```bash
uv run confluence-markdown --action read 'https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681034' --config --raw --quiet | head -30
```

````output
Title: Konfiguration
Space: Jan Vanvinkenroye (~ac118465)
Version: 2
URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681034

Markdown Content:
==================================================
# Konfiguration

## Config-Datei

`~/.config/icingaclient/config.toml`

```
[api]
url = "https://icinganfl.tik.uni-stuttgart.de/monitoring/list"

[auth]
cert = "~/.config/icingaclient/ac118465.crt"
key = "~/.config/icingaclient/ac118465.key"

[display]
format = "table"

[notifications]
notify_recovery = true

```

## Umgebungsvariablen
````

## Seitenhierarchie — `list-children` zeigt die Unterseiten einer Seite (hier die gestern angelegte Icinga-Client-Doku):

```bash
uv run confluence-markdown --action list-children 'https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681036' --config --quiet
```

```output
Found 6 child pages:

  - CLI-Kommandos
    ID: 1181680632
    URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181680632

  - Desktop-Benachrichtigungen
    ID: 1181681033
    URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681033

  - Entwicklung
    ID: 1181681035
    URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681035

  - Icinga Client - Überblick
    ID: 1181680606
    URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181680606

  - Konfiguration
    ID: 1181681034
    URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681034

  - Übersicht Widget
    ID: 1181680633
    URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181680633

```

## Seite als Datei herunterladen — `download` schreibt die Seite als Markdown-Datei mit Metadaten-Header:

```bash
uv run confluence-markdown --action download 'https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681036' --config --quiet -o /tmp/icinga-client.md && head -12 /tmp/icinga-client.md
```

```output
Content saved to: /tmp/icinga-client.md
Page URL: https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681036
# Icinga Client

**Space:** Jan Vanvinkenroye
**Page ID:** 1181681036
**Version:** 1
**URL:** https://wisman.izus.uni-stuttgart.de/pages/viewpage.action?pageId=1181681036

---

# Icinga Client

CLI-Tool und macOS-Widget für das Icinga-Monitoring des TIK (`icinganfl.tik.uni-stuttgart.de`). Zeigt Host- und Service-Status im Terminal, überwacht Änderungen im Watch-Modus und sendet Desktop-Benachrichtigungen bei Problemen.
```

## MCP-Server — derselbe Client ist als MCP-Server für Claude & Co. verfügbar (`uvx --from 'confluence-markdown[mcp]' confluence-markdown-mcp`). Ein JSON-RPC-Handshake über stdio zeigt die 18 Tools:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"demo","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
| uv run confluence-markdown-mcp 2>/dev/null \
| python3 -c "
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get('id') == 2:
        tools = msg['result']['tools']
        print(f'{len(tools)} Tools:')
        for t in tools:
            print(' -', t['name'])
"
```

```output
18 Tools:
 - check_elicitation_support
 - search_pages
 - list_recent_pages
 - list_spaces
 - list_children
 - get_page_storage
 - edit_page_storage
 - create_page_storage
 - add_content_storage
 - get_page_md
 - edit_page_md
 - create_page_md
 - add_content_md
 - move_page
 - delete_page
 - list_attachments
 - download_attachment
 - upload_attachment
```

## Qualitätssicherung — Linting und die komplette Testsuite (134 Tests, u. a. Async-Batch, Rate-Limit- und Keyring-Fallback-Pfade):

```bash
uv run ruff check src/ tests/ && uv run pytest -q 2>&1 | tail -1 | sed 's/ in .*s//'
```

```output
All checks passed!
134 passed
```

Damit ist der komplette Workflow gezeigt: Auth über Schlüsselbund-Profil, Seiten lesen/herunterladen, Hierarchie navigieren, MCP-Server mit 18 Tools, grüne Testsuite. Reproduzierbar mit `showboat verify demo/demo.md` (die Live-Abschnitte hängen vom aktuellen Confluence-Inhalt ab).
