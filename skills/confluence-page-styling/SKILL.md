---
name: confluence-page-styling
description: Erstellt und stylt Confluence-Data-Center-Seiten im Storage-Format (XHTML) über den confluence-markdown MCP - mit Panels, Inhaltsverzeichnis, Code-Macros, Status-Lozenges, Tabellen und Seitenhierarchien. Verwenden, wenn der User Seiten in Confluence anlegen, dokumentieren, "im Bereich X ablegen", stylen oder überarbeiten will (z. B. "dokumentiere das Projekt in Confluence", "leg dazu eine Seite im Bereich Y an", "überarbeite die Seite mit Panels/Lozenges").
---

# Confluence Page Styling

Seiten in Confluence Data Center anlegen und professionell stylen. Werkzeug ist der
`confluence-markdown` MCP-Server (Tools `mcp__confluence-markdown__*`); das native
Seitenformat ist das Confluence-Storage-Format (XHTML mit `ac:`/`ri:`-Elementen).

## Workflow

1. **Tools laden**: Per ToolSearch in EINEM Aufruf laden:
   `select:mcp__confluence-markdown__list_spaces,mcp__confluence-markdown__search_pages,mcp__confluence-markdown__create_page_storage,mcp__confluence-markdown__edit_page_storage,mcp__confluence-markdown__list_children,mcp__confluence-markdown__get_page_storage`
2. **Bereich verifizieren**: `search_pages` mit CQL `space = "KEY" and type = page`
   oder `list_spaces`. Persönliche Bereiche heißen `~username` (z. B. `~ac118465`) -
   wenn der User nur "Bereich ac118465" sagt, ist meist `~ac118465` gemeint.
3. **Hierarchie planen**: Eine Hauptseite (Übersicht) mit Unterseiten pro Thema.
   Erst die Hauptseite anlegen, deren `id` aus der Antwort als `parent_id` für die
   Unterseiten verwenden. Seitentitel müssen bereichsweit eindeutig sein -
   Unterseiten daher mit Präfix benennen ("Projekt X - README").
4. **Seiten im Storage-Format anlegen** (`create_page_storage`), nicht erst Markdown
   und dann umbauen. Vor dem Überschreiben bestehender Seiten mit
   `edit_page_storage` immer erst `get_page_storage` lesen.
5. **Verifizieren**: `list_children` auf der Hauptseite; URLs aus den Antworten dem
   User als klickbare Links zurückgeben.

Alle Macro-Snippets, Tabellen-Syntax und Escaping-Regeln:
[references/storage-format.md](references/storage-format.md) - vor dem Schreiben
der ersten Seite lesen.

## Style-Konventionen

- **Hauptseite**: Panel-Macro als Kopf (Navy `#1F4E79`, weiße Titelschrift),
  Steckbrief-Tabelle (Repository, Sprache, Tooling, Stand), Feature-Liste,
  `children`-Macro statt manueller Unterseiten-Liste, Info-Panel für Hinweise.
- **Inhaltsseiten**: `toc`-Macro (maxLevel 2) an den Anfang, `h1`/`h2` als Struktur.
- **Code und Befehle**: immer `code`-Macro mit `language`-Parameter (bash, python,
  yaml, text ...), nie `<pre>`.
- **Hinweise**: `info` (neutral), `note` (beachten), `warning` (Gefahr/Secrets),
  `tip` (Empfehlung) - sparsam, maximal ein Panel pro Abschnitt.
- **Bewertungen/Status**: Status-Lozenges statt Farbtext. Ampel-Mapping für
  Ratings: niedrig=Green, mittel=Blue, hoch=Yellow, sehr hoch=Red.
- **Zahlen**: deutsches Format (Tausenderpunkt: 71.883; Dezimalkomma: 42,4),
  geschütztes Leerzeichen `&#160;` vor Einheiten und in "z.&#160;B.".
- **Typografie**: deutsche Anführungszeichen `&#8222;...&#8220;`, Gedankenstrich
  `&#8211;`, Pfeil `&#8594;` - Sonderzeichen als numerische Entities schreiben,
  Umlaute (ä/ö/ü/ß) sind dagegen direkt in UTF-8 sicher.
- **Links auf Bereiche**: `https://<base>/display/KEY`; auf Seiten:
  `.../pages/viewpage.action?pageId=<id>`.

## Wichtige Regeln

- Storage-Format muss **wohlgeformtes XHTML** sein - jedes Tag schließen,
  Attribute in Anführungszeichen, `&` als `&amp;`, `<`/`>` in Fließtext als
  `&lt;`/`&gt;`. Der MCP validiert lokal und lehnt kaputtes XHTML ab.
- Kein `<html>`, `<head>` oder `<body>` - nur der Seiteninhalt.
- Die `*_md`-Tools nur für schnelle, simple Seiten ohne Macros; für alles
  Gestylte die `*_storage`-Tools.
- Attachments kann der MCP nicht hochladen - Dateiinhalte stattdessen als
  Tabellen/Exzerpte einarbeiten und den User auf manuellen Upload hinweisen.
- Schreiboperationen (create/edit/move/delete) verändern ein Produktivsystem:
  nur ausführen, was der User beauftragt hat; vor dem Überschreiben fremder
  bestehender Seiten nachfragen.
