# Confluence-Storage-Format: Macro- und Syntax-Referenz

Getestete Snippets für Confluence Data Center (`representation: "storage"`).
Alle Beispiele sind wohlgeformtes XHTML und können direkt in
`create_page_storage` / `edit_page_storage` verwendet werden.

## Inhalt

1. [Panels (info, note, warning, tip, panel)](#panels)
2. [Inhaltsverzeichnis (toc)](#inhaltsverzeichnis)
3. [Code-Blöcke](#code-blöcke)
4. [Status-Lozenges](#status-lozenges)
5. [Tabellen](#tabellen)
6. [Kindseiten-Macro](#kindseiten-macro)
7. [Expand (Aufklappbereich)](#expand)
8. [Links](#links)
9. [Bilder und Attachments](#bilder-und-attachments)
10. [Escaping und Entities](#escaping-und-entities)
11. [Beispiel einer kompletten Hauptseite](#beispiel-hauptseite)

## Panels

Farbige Hinweisboxen. Body ist Rich-Text (`ac:rich-text-body`), darf also
Absätze, Listen, Code usw. enthalten.

```xml
<ac:structured-macro ac:name="info"><ac:rich-text-body>
  <p>Neutraler Hinweis.</p>
</ac:rich-text-body></ac:structured-macro>

<ac:structured-macro ac:name="note"><ac:rich-text-body>
  <p>Zu beachten (gelb).</p>
</ac:rich-text-body></ac:structured-macro>

<ac:structured-macro ac:name="warning"><ac:rich-text-body>
  <p>Warnung (rot) - z. B. Secrets-Hinweise.</p>
</ac:rich-text-body></ac:structured-macro>

<ac:structured-macro ac:name="tip"><ac:rich-text-body>
  <p>Empfehlung (grün).</p>
</ac:rich-text-body></ac:structured-macro>
```

Frei gestaltbares Panel mit Titelzeile (für Seitenköpfe im Corporate-Stil):

```xml
<ac:structured-macro ac:name="panel">
  <ac:parameter ac:name="borderColor">#1F4E79</ac:parameter>
  <ac:parameter ac:name="titleBGColor">#1F4E79</ac:parameter>
  <ac:parameter ac:name="titleColor">#FFFFFF</ac:parameter>
  <ac:parameter ac:name="title">Seitentitel im Panel-Kopf</ac:parameter>
  <ac:rich-text-body><p>Einleitungstext.</p></ac:rich-text-body>
</ac:structured-macro>
```

## Inhaltsverzeichnis

```xml
<ac:structured-macro ac:name="toc"><ac:parameter ac:name="maxLevel">2</ac:parameter></ac:structured-macro>
```

`maxLevel` 1-3 je nach Seitentiefe; ganz an den Seitenanfang.

## Code-Blöcke

Immer das `code`-Macro, nie `<pre>`. Der Code steht in CDATA und braucht
darin KEIN Escaping (auch `<`, `>`, `&` nicht). Achtung: enthält der Code
selbst die Sequenz `]]>`, muss sie aufgeteilt werden (`]]]]><![CDATA[>`).

```xml
<ac:structured-macro ac:name="code">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[uv run confluence-stats --help
# Kommentare und <spitze Klammern> sind hier erlaubt]]></ac:plain-text-body>
</ac:structured-macro>
```

Sprachen (DC-Standard): bash, python, java, js, sql, yaml, xml, html, json,
text. Optional: `<ac:parameter ac:name="title">Dateiname</ac:parameter>` und
`<ac:parameter ac:name="linenumbers">true</ac:parameter>`.

## Status-Lozenges

Kompakte farbige Badges, auch innerhalb von Tabellenzellen:

```xml
<ac:structured-macro ac:name="status">
  <ac:parameter ac:name="colour">Green</ac:parameter>
  <ac:parameter ac:name="title">niedrig</ac:parameter>
</ac:structured-macro>
```

Verfügbare Farben (exakt so geschrieben, britisch `colour`): `Grey`, `Red`,
`Yellow`, `Green`, `Blue`.

Ampel-Mapping für vierstufige Ratings: niedrig=Green, mittel=Blue,
hoch=Yellow, sehr hoch=Red. Optional `<ac:parameter ac:name="subtle">true</ac:parameter>`
für die dezente Variante.

## Tabellen

Standard-HTML; `<th>` funktioniert sowohl als Kopfzeile als auch als
Kopfspalte. Kein `<thead>` nötig, `<tbody>` reicht.

```xml
<table><tbody>
<tr><th>Spalte A</th><th>Spalte B</th></tr>
<tr><td>Wert</td><td>Wert</td></tr>
</tbody></table>
```

Steckbrief-Muster (Kopfspalte links):

```xml
<table><tbody>
<tr><th>Repository</th><td><code>~/pfad/zum/repo</code></td></tr>
<tr><th>Sprache</th><td>Python &#8805; 3.11</td></tr>
</tbody></table>
```

`colspan`/`rowspan` werden im Storage-Format verlustfrei unterstützt.
Zellen dürfen Macros enthalten (z. B. Status-Lozenges).

## Kindseiten-Macro

Listet Unterseiten automatisch - auf Übersichtsseiten immer dies statt
manuell gepflegter Listen:

```xml
<ac:structured-macro ac:name="children"><ac:parameter ac:name="all">true</ac:parameter></ac:structured-macro>
```

## Expand

Aufklappbarer Abschnitt für Details, die den Lesefluss stören würden:

```xml
<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">Details anzeigen</ac:parameter>
  <ac:rich-text-body><p>Eingeklappter Inhalt.</p></ac:rich-text-body>
</ac:structured-macro>
```

## Links

Externe URLs und absolute Instanz-URLs als normales `<a href="...">`:

```xml
<a href="https://wisman.example.de/display/KEY">Bereich KEY</a>
<a href="https://wisman.example.de/pages/viewpage.action?pageId=123456">Seite</a>
```

Instanzinterne Seitenlinks robust gegen Umbenennung per `ac:link`
(rendert als Seitentitel, folgt bei Verschiebung):

```xml
<ac:link><ri:page ri:content-title="Titel der Zielseite" /></ac:link>
<ac:link><ri:page ri:space-key="KEY" ri:content-title="Titel" /></ac:link>
```

Nutzer verlinken/erwähnen:

```xml
<ac:link><ri:user ri:username="ac118465" /></ac:link>
```

## Bilder und Attachments

Der confluence-markdown MCP kann KEINE Dateien anhängen. Bilder nur
referenzieren, wenn das Attachment bereits auf der Seite existiert:

```xml
<ac:image><ri:attachment ri:filename="diagramm.png" /></ac:image>
<ac:image ac:width="600"><ri:url ri:value="https://example.org/extern.png" /></ac:image>
```

Für Berichte/Dateien: Inhalte als Tabellen und Exzerpte in die Seite
einarbeiten, den User für die Originaldatei auf manuellen Upload hinweisen.

## Escaping und Entities

Grundregel: wohlgeformtes XHTML. Der MCP validiert vor dem Upload und lehnt
Fehler lokal ab (kein HTTP 400 vom Server).

| Zeichen im Fließtext | Schreiben als |
|---|---|
| `&` | `&amp;` |
| `<` / `>` | `&lt;` / `&gt;` |
| `"` (in Fließtext um Code) | `&quot;` |
| Gedankenstrich – | `&#8211;` |
| Anführungszeichen „ … " | `&#8222;` … `&#8220;` |
| Pfeil → | `&#8594;` |
| Multiplikationspunkt · | `&#183;` |
| Ø | `&#216;` |
| ≥ / ≤ | `&#8805;` / `&#8804;` |
| … | `&#8230;` |
| geschütztes Leerzeichen | `&#160;` |

- Umlaute und ß direkt als UTF-8 schreiben (kein Escaping nötig).
- Selbstschließende Tags mit Slash: `<ri:page ... />`, `<br />`.
- HTML-Entities wie `&nbsp;` gibt es im XHTML NICHT - numerisch schreiben (`&#160;`).
- In CDATA (Code-Macros) gilt kein Escaping.

## Beispiel Hauptseite

Muster einer Projektdoku-Hauptseite (Panel-Kopf, Steckbrief, Features,
automatische Unterseiten-Liste):

```xml
<ac:structured-macro ac:name="panel">
  <ac:parameter ac:name="borderColor">#1F4E79</ac:parameter>
  <ac:parameter ac:name="titleBGColor">#1F4E79</ac:parameter>
  <ac:parameter ac:name="titleColor">#FFFFFF</ac:parameter>
  <ac:parameter ac:name="title">Projektname</ac:parameter>
  <ac:rich-text-body><p>Ein-Absatz-Beschreibung des Projekts.</p></ac:rich-text-body>
</ac:structured-macro>
<table><tbody>
<tr><th>Repository</th><td><code>~/pfad</code></td></tr>
<tr><th>Sprache</th><td>Python &#8805; 3.11</td></tr>
<tr><th>Stand</th><td>Juli 2026</td></tr>
</tbody></table>
<h1>Features</h1>
<ul><li>Feature A</li><li><strong>Feature B</strong> (0&#8211;100)</li></ul>
<h1>Dokumentation</h1>
<ac:structured-macro ac:name="children"><ac:parameter ac:name="all">true</ac:parameter></ac:structured-macro>
<ac:structured-macro ac:name="info"><ac:rich-text-body>
  <p>Hinweis auf die wichtigste Unterseite.</p>
</ac:rich-text-body></ac:structured-macro>
```
