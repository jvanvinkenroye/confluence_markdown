# Confluence Data Center Markdown Tool

A Python CLI tool to download, read, edit, and manage Confluence Data Center pages with markdown support.

## Features

### Core Features
- Download Confluence pages as markdown files
- Read page content directly in terminal with Rich rendering
- Edit pages in your preferred editor (vim, VS Code, nano, etc.)
- Add content to existing pages (markdown or HTML)
- Create new pages with templates (interactive space and parent selection)
- Create task pages with Page Properties macro

### Navigation & Search
- Interactive page selection with fzf or InquirerPy
- Browse recently viewed pages
- Edit recently edited pages
- Search pages by text or CQL query
- List child pages (with recursive option)

### Batch Operations
- Download entire page trees recursively
- Parallel API calls for faster batch operations
- Export multiple pages to a directory

### Quality of Life
- Response caching for faster repeated access
- Per-space configuration (different editors/settings per space)
- Shell tab completion (bash/zsh)
- Rate limiting and automatic retry on errors
- Complex table preservation (colspan/rowspan)
- YAML table format for easier editing

### Configuration
- Save credentials in config file
- Multiple configuration profiles
- Space-specific settings

## Installation

### Using uv tool (recommended)

```bash
# Clone the repository
git clone https://github.com/jvanvinkenroye/confluence_markdown.git
cd confluence_markdown

# Install globally
uv tool install --editable .

# Now use from anywhere
confluence-markdown --help
```

### Using uv (development)

```bash
cd confluence_markdown
uv sync
uv run confluence-markdown --help
```

### Enable Tab Completion

```bash
# For bash - add to ~/.bashrc
eval "$(register-python-argcomplete confluence-markdown)"

# For zsh - add to ~/.zshrc
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete confluence-markdown)"
```

## Quick Start

### 1. Save your credentials

```bash
confluence-markdown \
  --base-url https://confluence.company.com \
  --username YOUR_USERNAME \
  --token YOUR_PAT \
  --save-config \
  --action test-auth
```

### 2. Browse recent pages

```bash
# Interactive selection with fzf
confluence-markdown --action read-recent

# Use arrow keys if fzf not installed
confluence-markdown --action read-recent --no-fzf
```

### 3. Edit a page

```bash
confluence-markdown --action edit "https://confluence.company.com/pages/viewpage.action?pageId=12345"
```

## Usage Examples

### Reading Pages

```bash
# Browse recently viewed pages (default action)
confluence-markdown

# Read specific page
confluence-markdown --action read "PAGE_URL"

# Read with raw markdown output
confluence-markdown --action read-recent --raw

# Search and read
confluence-markdown --action search --query "deployment guide"
```

### Editing Pages

```bash
# Edit specific page
confluence-markdown --action edit "PAGE_URL"

# Edit with specific editor
confluence-markdown --action edit --editor "code --wait" "PAGE_URL"

# Edit with YAML tables (easier to edit complex tables)
confluence-markdown --action edit --table-format yaml "PAGE_URL"

# Select from recently edited pages
confluence-markdown --action edit-recent --limit 20
```

### Downloading Pages

```bash
# Download single page
confluence-markdown --action download -o page.md "PAGE_URL"

# Download page and all children (parallel)
confluence-markdown --action download --recursive --output-dir ./export "PAGE_URL"

# Download with custom limit
confluence-markdown --action download --recursive --limit 100 --output-dir ./export "PAGE_URL"
```

### Listing Child Pages

```bash
# List direct children
confluence-markdown --action list-children "PAGE_URL"

# List all descendants recursively (uses parallel API calls)
confluence-markdown --action list-children --recursive "PAGE_URL"
```

### Creating Pages

```bash
# Fully interactive: select space and parent page via fzf
confluence-markdown --action create-edit

# Non-interactive: all parameters provided
confluence-markdown --action create \
  --space MYSPACE \
  --title "My New Page" \
  --content "# Welcome\n\nPage content here"

# Create child page (parent-id known)
confluence-markdown --action create \
  --space MYSPACE \
  --title "Child Page" \
  --parent-id 12345 \
  --content "Content for child page"

# Create task page with Page Properties
confluence-markdown --action create-task \
  --parent-id 12345 \
  --title "New Task" \
  --category "Development" \
  --priority "80" \
  --status "offen" \
  --content "Task description here"
```

### Adding Content

```bash
# Append markdown content
confluence-markdown --action add \
  --content "## New Section\n\nNew content here" \
  "PAGE_URL"

# Prepend content
confluence-markdown --action add --prepend \
  --content "## Important Notice\n\nThis goes at the top" \
  "PAGE_URL"

# Add HTML directly
confluence-markdown --action add \
  --content "<ac:structured-macro ac:name='info'>...</ac:structured-macro>" \
  --content-type html \
  "PAGE_URL"
```

### Search

```bash
# Text search
confluence-markdown --action search --query "kubernetes deployment" --limit 20

# CQL search
confluence-markdown --action search --cql "space = DEV AND label = important"

# Search in specific space
confluence-markdown --action search --cql "space = DOCS AND text ~ 'API'"
```

### Caching

```bash
# Disable cache for fresh data
confluence-markdown --no-cache --action read-recent

# Clear all cached data
confluence-markdown --clear-cache
```

### Scripting Mode

```bash
# Quiet mode for scripts (suppress info messages)
confluence-markdown --quiet --action download -o page.md "PAGE_URL"

# Check exit code
if confluence-markdown --quiet --action test-auth; then
  echo "Auth OK"
fi
```

## Configuration

### Config File Location

`~/.config/confluence-markdown/config.json`

### Multiple Profiles

```bash
# Save work profile
confluence-markdown \
  --base-url https://work.confluence.com \
  --username work_user \
  --token WORK_TOKEN \
  --save-config --profile work \
  --action test-auth

# Use work profile
confluence-markdown --profile work --action read-recent

# List profiles
confluence-markdown --list-profiles

# Delete profile
confluence-markdown --delete-profile --profile old
```

### Per-Space Configuration

Edit `~/.config/confluence-markdown/config.json`:

```json
{
  "default": {
    "base_url": "https://confluence.company.com",
    "username": "user",
    "token": "...",
    "editor": "vim",
    "table_format": "markdown",
    "spaces": {
      "DOCS": {
        "editor": "code --wait",
        "table_format": "yaml"
      },
      "WIKI": {
        "editor": "nano"
      }
    }
  }
}
```

Now pages in the DOCS space will open in VS Code with YAML tables.

## Command Line Reference

```
Actions:
  read-recent     Browse recently viewed pages (default)
  edit-recent     Edit recently edited pages
  read            Read specific page
  edit            Edit specific page
  download        Download page as markdown
  add             Add content to page
  create          Create new page
  create-task     Create task page with Page Properties
  search          Search pages
  list-children   List child pages
  test-auth       Test authentication

Options:
  --base-url URL        Confluence base URL
  --username USER       Username for auth
  --token TOKEN         Personal Access Token
  --password PASS       Password (alternative to token)
  --profile NAME        Config profile (default: "default")
  --config              Load from config file explicitly

  --action ACTION       Action to perform
  --output, -o FILE     Output file for download
  --content TEXT        Content for add/create
  --content-type TYPE   markdown (default) or html

  --space KEY           Space key for create
  --title TEXT          Page title for create
  --parent-id ID        Parent page ID

  --category TEXT       Task category (create-task)
  --priority TEXT       Task priority (create-task)
  --status TEXT         Task status (create-task)

  --query TEXT          Search query text
  --cql TEXT            CQL query for search
  --limit N             Number of results (default: 10)

  --recursive, -r       Process children recursively
  --output-dir DIR      Output directory for batch downloads

  --editor CMD          Editor command (e.g., "vim", "code --wait")
  --table-format FMT    Table format: markdown or yaml
  --raw                 Output raw markdown
  --width N             Override terminal width

  --no-fzf              Use InquirerPy instead of fzf
  --no-cache            Disable response caching
  --clear-cache         Clear cache and exit

  --quiet, -q           Suppress info messages
  --verbose             Enable debug output
  --completion SHELL    Output completion script (bash/zsh)

Config Management:
  --init-config         Create example config file
  --save-config         Save credentials to config
  --list-profiles       List all profiles
  --delete-profile      Delete profile specified by --profile
```

## MCP Server (Claude Desktop / AI agents)

The tool can run as an [MCP](https://modelcontextprotocol.io/) stdio server, exposing Confluence operations as tools that Claude and other MCP clients can call directly.

### Install the MCP extra

```bash
uv pip install -e ".[mcp]"
```

### Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "/absolute/path/to/.venv/bin/confluence-markdown-mcp"
    }
  }
}
```

The server reuses your saved config profile automatically (same credentials as the CLI). If you haven't saved credentials yet, run `confluence-markdown --save-config` first, or pass credentials via environment variables:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "/absolute/path/to/.venv/bin/confluence-markdown-mcp",
      "env": {
        "CONFLUENCE_URL": "https://wiki.example.com",
        "CONFLUENCE_USERNAME": "user",
        "CONFLUENCE_TOKEN": "PAT"
      }
    }
  }
}
```

Restart Claude Desktop after editing the config file.

### Available MCP tools

| Tool | Description |
|------|-------------|
| `search_pages` | Search via CQL or free-text query |
| `get_page` | Get full page content (markdown + metadata) by URL |
| `list_recent_pages` | Pages recently modified by you |
| `list_spaces` | All accessible spaces |
| `list_children` | Direct child pages of a page |
| `create_page` | Create a new page with markdown content |
| `edit_page` | Replace a page's full content |
| `add_content_to_page` | Append or prepend content to a page |

Pages are also accessible as MCP resources via `confluence://page/{page_id}`.

### MCP Troubleshooting

**Tools time out in Claude Desktop** — The MCP server process is started once per Claude Desktop session and does not auto-restart after long idle periods. If tool calls fail or time out, restart Claude Desktop to re-establish the connection.

**Server fails to start** — Check that the `mcp` extra is installed and credentials are configured:

```bash
# Verify the binary works
confluence-markdown-mcp  # should block waiting for stdin (Ctrl-C to exit)

# Verify credentials
confluence-markdown --action test-auth
```

**`create_page` or `edit_page` returns no output** — These operations print progress to stdout, which would corrupt the MCP JSON-RPC channel. The server automatically redirects such output to stderr so it only appears in `~/Library/Logs/Claude/mcp-server-confluence.log`.

---

## Requirements

- Python 3.10+
- httpx
- requests
- markdownify
- beautifulsoup4
- InquirerPy
- rich
- tenacity
- argcomplete
- pyyaml
- markdown
- keyring (credential storage)

Optional:
- fzf (for fuzzy page selection)
- mcp (for MCP server support — `uv pip install -e ".[mcp]"`)

## Troubleshooting

### Authentication Errors

```bash
# Test credentials
confluence-markdown --verbose --action test-auth

# For Data Center, always use username + token
confluence-markdown --username USER --token PAT --action test-auth
```

### Rate Limiting

The tool automatically handles rate limits with exponential backoff. If you hit limits frequently:

```bash
# Add delays between batch operations
confluence-markdown --action download --recursive --limit 50 "PAGE_URL"
```

### Cache Issues

```bash
# Clear cache if data seems stale
confluence-markdown --clear-cache

# Disable cache for single command
confluence-markdown --no-cache --action read "PAGE_URL"
```

### Complex Tables

Tables with merged cells (colspan/rowspan) are preserved as HTML with a comment marker:

```html
<!-- Complex table preserved as HTML (has merged cells) -->
<table>...</table>
```

## License

WTFPL - Do What The Fuck You Want To Public License
