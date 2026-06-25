# Claude Code Marketplace Distribution

This document describes how to distribute `confluence-markdown-mcp` via the Claude Code Marketplace.

## Prerequisites

1. **GitHub Repository** (already set up at https://github.com/jvanvinkenroye/confluence_markdown)
2. **PyPI Account** with API token for publishing Python packages
3. **GitHub Secrets** configured:
   - `PYPI_TOKEN`: Your PyPI API token (with scope "Entire account")

## Setup GitHub Secrets

1. Go to: https://github.com/jvanvinkenroye/confluence_markdown/settings/secrets/actions
2. Add new secret:
   - **Name:** `PYPI_TOKEN`
   - **Value:** Your PyPI API token (from https://pypi.org/account/token/)

## Creating a Release

### 1. Update Version

Edit `pyproject.toml`:

```toml
[project]
version = "0.2.0"  # Bump version
```

### 2. Create Release Notes

Create/update `RELEASE_NOTES.md`:

```markdown
# v0.2.0 — Enhanced MCP Server

## Features

- ✨ New `*_storage` tools for lossless XHTML access
- ✨ Human-in-the-loop write confirmation (elicitation support)
- 🐛 Fixed colspan/rowspan preservation in tables
- 📚 Comprehensive documentation for Claude Code & Desktop

## Installation

### Claude Code / Desktop

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

### Command Line

```bash
uvx --from "git+https://github.com/jvanvinkenroye/confluence_markdown.git@v0.2.0[mcp]" confluence-markdown-mcp
```

## Tools

13 MCP tools available:
- Navigation: `list_spaces`, `list_recent_pages`, `search_pages`, `list_children`
- Read: `get_page_storage`, `get_page_md`
- Write: `create_page_*`, `edit_page_*`, `add_content_*`
- Diagnostic: `check_elicitation_support`

## Resources

- `confluence://page/{page_id}` — Markdown view
- `confluence://page/{page_id}/storage` — XHTML view (lossless)

## Known Issues

- Elicitation (write confirmation) not yet supported by all clients
- Some Confluence macros may cause 500 errors on older server versions

## Contributors

- Jan Vanvinkenroye (@jvanvinkenroye)
```

### 3. Commit and Tag

```bash
git add pyproject.toml RELEASE_NOTES.md
git commit -m "chore: prepare v0.2.0 release"
git tag -a v0.2.0 -m "Version 0.2.0: Enhanced MCP Server"
git push origin main --tags
```

The GitHub Actions workflow will automatically:
1. Build the Python package
2. Create a GitHub Release with artifacts
3. Publish to PyPI

## Registering in Claude Code Marketplace

### Step 1: Marketplace Registration (via Anthropic)

The Claude Code Marketplace is currently managed by Anthropic. To register:

1. Create an issue in the [Claude Code Marketplace Registry](https://github.com/anthropics/claude-code-marketplace)
2. Include:
   - **Title:** `[New Tool] confluence-markdown-mcp`
   - **Description:**
     ```
     MCP server for read/write access to Confluence Data Center pages
     
     - GitHub: https://github.com/jvanvinkenroye/confluence_markdown
     - PyPI: https://pypi.org/project/confluence-markdown/
     - Features: Storage format (lossless), Markdown, 13 tools
     ```
   - **Manifest:** Link to `mcp.json` in your repo
   - **Installation:** Command for users to install

### Step 2: Prepare Documentation

Ensure your README includes:
- ✅ Clear installation instructions
- ✅ MCP server setup for Claude Code and Claude Desktop
- ✅ All available tools documented
- ✅ Usage examples
- ✅ Authentication setup
- ✅ Troubleshooting

All covered in `/README.md`.

### Step 3: Marketplace Listing

Once approved, the tool will appear in Claude Code's marketplace with:
- **Name:** confluence-markdown-mcp
- **Description:** Read and write Confluence pages from Claude
- **Installation:** One-click install (configured from `mcp.json`)
- **Authentication:** Guided setup for Confluence credentials

## Distribution Channels

### Users Can Install Via:

1. **PyPI / uvx** (manual command):
   ```bash
   uvx --from "git+https://github.com/jvanvinkenroye/confluence_markdown.git[mcp]" confluence-markdown-mcp
   ```

2. **Claude Code Marketplace** (one-click, if approved):
   - Search "confluence-markdown"
   - Click "Install"
   - Follow credential setup

3. **Direct GitHub** (development):
   ```bash
   git clone https://github.com/jvanvinkenroye/confluence_markdown.git
   cd confluence_markdown
   uv pip install -e ".[mcp]"
   ```

4. **Homebrew** (optional, future):
   ```bash
   brew install confluence-markdown-mcp
   ```

## Update Process

1. Make changes in a branch
2. Update version in `pyproject.toml`
3. Update `RELEASE_NOTES.md`
4. Commit and push
5. Create git tag (`v0.2.0`)
6. Push tag: `git push origin v0.2.0`
7. GitHub Actions builds, tests, and publishes automatically

## Versioning

Follow [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Example: `0.2.1` → `0.2.2` (patch fix), `0.3.0` (new features), `1.0.0` (stable release)

## Support

- **Issues:** GitHub Issues (https://github.com/jvanvinkenroye/confluence_markdown/issues)
- **Discussions:** GitHub Discussions (enable in repo settings)
- **Documentation:** README.md and inline docstrings
