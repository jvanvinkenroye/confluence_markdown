# v0.2.0 — Page Organization & Deletion

## ✨ New Features

- **`move_page` tool** — Reorganize pages by changing their parent in the hierarchy
- **`delete_page` tool** — Move pages to trash (recoverable within 30 days)
- **Total: 15 MCP Tools** for complete Confluence workflow

## 🛠️ All Tools (15 total)

### Navigation & Search (4 tools)
- `list_spaces` — List all accessible Confluence spaces
- `list_recent_pages` — List recently modified pages
- `search_pages` — Search by CQL expression or free-text
- `list_children` — List child pages of a given page

### Read Pages (2 tools)
- `get_page_storage` — Get XHTML (lossless)
- `get_page_md` — Get Markdown (lossy but readable)

### Create Pages (2 tools)
- `create_page_storage` — Create with XHTML
- `create_page_md` — Create with Markdown

### Edit Pages (2 tools)
- `edit_page_storage` — Replace content (XHTML)
- `edit_page_md` — Replace content (Markdown)

### Add Content (2 tools)
- `add_content_storage` — Append/prepend XHTML
- `add_content_md` — Append/prepend Markdown

### Organize & Delete (2 tools) **NEW**
- `move_page` — Move a page to a new parent
- `delete_page` — Delete a page (to trash)

### Diagnostic (1 tool)
- `check_elicitation_support` — Check client capabilities

## 📋 Previous Features (from v0.1.0)

- **Dual Format Support:**
  - `*_storage` tools: Confluence storage format (XHTML) — lossless, preserves tables, macros, layouts
  - `*_md` tools: Markdown format — human-readable, convenient
- **Claude Desktop & Code Integration:** Full MCP server support
- **Human-in-the-Loop:** Write confirmation support (elicitation)
- **MCP Resources:** `confluence://page/{page_id}` and `/storage` variants

## 🔐 Security

- **Credentials:** Stored securely in macOS Keychain (or system keyring)
- **Write Protection:** Human-in-the-loop confirmation for all write operations (including move & delete)
- **No Logging:** Sensitive content never logged to disk

## 🐛 Known Limitations

- Some Confluence server versions (older) may reject certain macros with 500 errors
- Elicitation (write confirmation) not yet supported in all MCP clients
- Offline mode not supported (requires live Confluence connection)
- `move_page` changes only parent, not title or content

## 📦 Installation

### via uvx (Recommended)

```bash
uvx confluence-markdown-mcp
```

### Manual Setup

```bash
git clone https://github.com/jvanvinkenroye/confluence_markdown.git
cd confluence_markdown
uv pip install -e ".[mcp]"
```

See README.md for detailed setup instructions and configuration for Claude Desktop/Code.

## 🙏 Thanks

Built with:
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/jlopp/fastmcp) for easy server implementation
- [markdownify](https://github.com/matthewwithanm/python-markdownify) for HTML↔Markdown conversion
- [Confluence REST API](https://developer.atlassian.com/cloud/confluence/rest/v2/)

## 📝 License

WTFPL - Do What The Fuck You Want To Public License
