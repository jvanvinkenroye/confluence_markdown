# Supported Content Types

This document describes what content types and formats work with the confluence-markdown tool.

## Content Type Modes

The tool supports two content type modes via `--content-type`:

### 1. Markdown Mode (default)
```bash
--content-type markdown
```
Converts markdown to Confluence HTML storage format.

### 2. HTML Mode
```bash
--content-type html
```
Passes HTML directly to Confluence without conversion.

## Supported Markdown Features ✅

Based on testing with localhost:8090, the following markdown features work:

### Headers
```markdown
# H1 Header
## H2 Header
### H3 Header
#### H4 Header
```
✅ All header levels supported

### Tables
```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |
```
✅ **Tables work!** (Fixed in commit 94a654e)
- Uses Python markdown library with `tables` extension
- Supports header rows with alignment

### Code Blocks

**Fenced code blocks:**
````markdown
```python
def hello():
    print("Hello, World!")
```
````
✅ Supported via `fenced_code` extension

**Inline code:**
```markdown
Use `variable_name` for inline code
```
✅ Fully supported

### Lists

**Unordered:**
```markdown
- Item 1
- Item 2
  - Nested item
```
✅ Supported with nesting

**Ordered:**
```markdown
1. First item
2. Second item
3. Third item
```
✅ Supported with nesting

### Text Formatting

```markdown
**Bold text**
*Italic text*
***Bold and italic***
~~Strikethrough~~ (may vary by Confluence version)
```
✅ Bold and italic confirmed working
⚠️  Strikethrough depends on Confluence version

### Links

```markdown
[Link text](https://example.com)
[Link with title](https://example.com "Title text")
```
✅ Fully supported

### Blockquotes

```markdown
> This is a blockquote
> Multiple lines
```
✅ Fully supported

### Horizontal Rules

```markdown
---
***
___
```
✅ Supported

## Limited or Unsupported Features ⚠️

### Images

```markdown
![Alt text](https://example.com/image.jpg)
![Alt text](https://example.com/image.jpg "Title")
```
⚠️  **Limited support**
- External image URLs work (images hosted elsewhere)
- Local image references don't upload the file
- No automatic image upload to Confluence

### Attachments

❌ **NOT SUPPORTED**
- Cannot upload attachments via this tool
- Cannot reference existing attachments
- No API for attachment management implemented

See TODO.md line 162 for planned attachment support.

### Task Lists

```markdown
- [ ] Incomplete task
- [x] Completed task
```
⚠️  **May not render properly**
- Converted to regular list items
- Confluence has its own task macro format

### Definition Lists

```markdown
Term
: Definition
```
❌ **Not supported** in standard markdown

### Footnotes

```markdown
Text with footnote[^1]

[^1]: Footnote content
```
❌ **Not supported** without additional extensions

### Math/LaTeX

```markdown
$$E = mc^2$$
```
❌ **Not supported**
- Confluence uses different math macros
- Would need custom handling

## HTML Content Type

When using `--content-type html`, you can use raw Confluence storage format HTML:

```bash
--content-type html --content '<h2>Title</h2><p>Content</p>'
```

### HTML Features Supported

✅ All standard HTML tags:
- Headers: `<h1>`, `<h2>`, etc.
- Paragraphs: `<p>`
- Lists: `<ul>`, `<ol>`, `<li>`
- Tables: `<table>`, `<tr>`, `<td>`, `<th>`
- Formatting: `<strong>`, `<em>`, `<code>`, `<pre>`
- Links: `<a href="">`

### Confluence Macros (Advanced)

You can insert Confluence macros using HTML:

```html
<ac:structured-macro ac:name="info">
  <ac:rich-text-body>
    <p>This is an info panel</p>
  </ac:rich-text-body>
</ac:structured-macro>
```

⚠️  Requires knowledge of Confluence storage format XML

## Conversion Details

### Markdown → HTML
- Uses Python `markdown` library (main.py:302)
- Extensions enabled:
  - `tables` - For table support
  - `fenced_code` - For code blocks
- Process: Markdown → HTML → Confluence storage format

### HTML → Markdown (when reading)
- Uses `markdownify` library (main.py:287)
- Settings:
  - `heading_style="ATX"` - Uses # headers
  - `bullets="-"` - Uses - for lists
  - Strips `<script>` and `<style>` tags

## Best Practices

### ✅ Recommended Content Types

1. **Text with basic formatting** (bold, italic, headers)
2. **Tables** (fully supported since commit 94a654e)
3. **Code blocks** (both inline and fenced)
4. **Lists** (ordered and unordered with nesting)
5. **Links** to external resources
6. **Blockquotes** for callouts

### ⚠️  Use With Caution

1. **Images** - Only external URLs work
2. **Complex HTML** - May not render correctly
3. **Confluence macros** - Require knowledge of storage format
4. **Mixed content** - Markdown + HTML can be unpredictable

### ❌ Not Supported

1. **File attachments** - No upload capability
2. **Local images** - Cannot upload to Confluence
3. **Task lists** - Use Confluence task macro instead
4. **Math equations** - Use Confluence math macro
5. **Diagrams** - Use Confluence diagram macros

## Examples

### Example 1: Simple Documentation

```bash
uv run confluence-markdown --config --profile localhost --action add \
  --content "# Project Documentation

## Overview
This project implements **elephant tracking** using GPS.

## Requirements
- Python 3.8+
- GPS module
- Data storage

## Installation
\`\`\`bash
pip install elephant-tracker
\`\`\`" \
  "http://localhost:8090/pages/viewpage.action?pageId=360451"
```

### Example 2: Data Table

```bash
uv run confluence-markdown --config --profile localhost --action add \
  --content "## Observation Data

| Date | Location | Count | Notes |
|------|----------|-------|-------|
| 2025-01-01 | Serengeti | 45 | Healthy herd |
| 2025-01-02 | Masai Mara | 23 | Young calves |
| 2025-01-03 | Amboseli | 67 | Near watering hole |" \
  "http://localhost:8090/pages/viewpage.action?pageId=360451"
```

### Example 3: HTML Content

```bash
uv run confluence-markdown --config --profile localhost --action add \
  --content-type html \
  --content '<h2>Alert</h2>
<p><strong>Warning:</strong> Elephant migration in progress.</p>
<ul>
  <li>Route: North to South</li>
  <li>Duration: 2 weeks</li>
  <li>Herd size: ~200</li>
</ul>' \
  "http://localhost:8090/pages/viewpage.action?pageId=360451"
```

## Limitations Summary

| Feature | Support | Notes |
|---------|---------|-------|
| Headers (H1-H6) | ✅ Full | All levels work |
| Tables | ✅ Full | Fixed in commit 94a654e |
| Code blocks | ✅ Full | Inline and fenced |
| Lists | ✅ Full | Ordered, unordered, nested |
| Bold/Italic | ✅ Full | Standard markdown |
| Links | ✅ Full | External URLs |
| Blockquotes | ✅ Full | Standard markdown |
| Images (external URL) | ⚠️  Partial | Links only, no upload |
| Images (local files) | ❌ None | No upload capability |
| Attachments | ❌ None | Not implemented |
| Task lists | ⚠️  Partial | Renders as plain list |
| Math/LaTeX | ❌ None | Use Confluence macros |
| Diagrams | ❌ None | Use Confluence macros |

## Future Enhancements

See TODO.md for planned features:
- Attachment upload/download (TODO.md:162)
- Image upload support
- Better handling of Confluence macros
- Support for more markdown extensions
