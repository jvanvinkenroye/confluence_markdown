# v0.1.0 — Initial MCP Release

## ✨ Features

- **13 MCP Tools** for reading/writing Confluence pages
- **Dual Format Support:**
  - `*_storage` tools: Confluence storage format (XHTML) — lossless, preserves tables, macros, layouts
  - `*_md` tools: Markdown format — human-readable, convenient
- **Claude Desktop Integration:** Full MCP server support
- **Claude Code Integration:** Settings-based configuration
- **Human-in-the-Loop:** Write confirmation support (elicitation)
- **MCP Resources:** `confluence://page/{page_id}` and `/storage` variants

## 🛠️ Tools Included

### Navigation & Search
- `list_spaces` — List all accessible Confluence spaces
- `list_recent_pages` — List recently modified pages
- `search_pages` — Search by CQL expression or free-text
- `list_children` — List child pages of a given page

### Read Pages
- `get_page_storage` — Get XHTML (lossless)
- `get_page_md` — Get Markdown (lossy but readable)

### Create Pages
- `create_page_storage` — Create with XHTML
- `create_page_md` — Create with Markdown

### Edit Pages
- `edit_page_storage` — Replace content (XHTML)
- `edit_page_md` — Replace content (Markdown)

### Add Content
- `add_content_storage` — Append/prepend XHTML
- `add_content_md` — Append/prepend Markdown

### Diagnostic
- `check_elicitation_support` — Check client capabilities

## 📚 Documentation

Complete guides available:
- **Installation:** See README.md
- **Configuration:** Setup for Claude Desktop & Claude Code
- **Usage Examples:** How to use tools in Claude
- **Troubleshooting:** Common issues and solutions
- **Format Comparison:** When to use storage vs markdown

## 🔐 Security

- **Credentials:** Stored securely in macOS Keychain (or system keyring)
- **Write Protection:** Human-in-the-loop confirmation for all write operations
- **No Logging:** Sensitive content never logged to disk

## 🐛 Known Limitations

- Some Confluence server versions (older) may reject certain macros with 500 errors
- Elicitation (write confirmation) not yet supported in all MCP clients
- Offline mode not supported (requires live Confluence connection)

## 📦 Installation

### via uvx (Recommended)

```bash
uvx --from "git+https://github.com/jvanvinkenroye/confluence_markdown.git[mcp]" confluence-markdown-mcp
```

### via PyPI (when published)

```bash
uvx confluence-markdown-mcp
```

### Manual Setup

```bash
git clone https://github.com/jvanvinkenroye/confluence_markdown.git
cd confluence_markdown
uv pip install -e ".[mcp]"
```

## 🚀 Quick Start

### 1. Configure Credentials

```bash
confluence-markdown \
  --base-url https://your-confluence.com \
  --username your_username \
  --token your_pat_token \
  --save-config \
  --action test-auth
```

### 2. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/confluence_markdown",
        "run",
        "confluence-markdown-mcp"
      ]
    }
  }
}
```

Then restart Claude Desktop.

### 3. Start Using

In Claude Desktop, just ask:
> "List my Confluence spaces"
> "Create a page about API design in the DOCS space"
> "Search for deployment guides"

Claude automatically uses the right MCP tools!

## 🙏 Thanks

Built with:
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/jlopp/fastmcp) for easy server implementation
- [markdownify](https://github.com/matthewwithanm/python-markdownify) for HTML↔Markdown conversion
- [Confluence REST API](https://developer.atlassian.com/cloud/confluence/rest/v2/)

## 📝 License

WTFPL - Do What The Fuck You Want To Public License
