# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A Python CLI tool for interacting with Confluence Data Center pages via REST API. The tool enables downloading pages as markdown, reading content, adding/editing content, and interactive editing with local text editors. It supports multiple authentication methods and configuration profiles.

## Architecture

### Core Components

**ConfluenceClient** (`src/confluence_markdown/main.py:27`) - Main API client
- Handles authentication (PAT, username/password, username+token for DC)
- REST API operations for page retrieval and updates
- Bidirectional HTML ↔ Markdown conversion using `markdownify` and `markdown` libraries
- Interactive editor integration for page editing

**ConfigManager** (`src/confluence_markdown/main.py:428`) - Configuration persistence
- Manages `~/.config/confluence-markdown/config.json`
- Supports multiple profiles for different Confluence instances
- Secure file permissions (0o600 for config file, 0o700 for directory)

### Authentication Flow

The client supports three authentication patterns:
1. **PAT with username** (Confluence DC 7.9+): `username:token` as Basic Auth - `main.py:49-52`
2. **Bearer token**: Token in Authorization header - `main.py:55-56`
3. **Username/password**: Standard Basic Auth - `main.py:58-62`

### URL Parsing

`_extract_page_id_from_url()` (`main.py:257`) supports multiple Confluence URL formats:
- `/pages/viewpage.action?pageId=123456` - Query parameter extraction
- `/spaces/SPACE/pages/123456/Page+Title` - Path-based ID extraction

### Content Conversion

**HTML → Markdown** (`_html_to_markdown()` at `main.py:287`):
- Uses BeautifulSoup for HTML parsing
- Converts to markdown with ATX-style headers and `-` bullets
- Strips script/style tags

**Markdown → HTML** (`_markdown_to_html()` at `main.py:302`):
- Uses Python `markdown` library with table and fenced_code extensions
- Critical for `--action add` and `--action edit` operations

### Interactive Edit Workflow

`edit_page_with_editor()` (`main.py:309`) implements:
1. Fetch current page content as markdown
2. Create temp file with metadata comments
3. Detect editor from `$EDITOR` or common editors (code, vim, nano, emacs, gedit)
4. Track file modification time to detect changes
5. Strip metadata and convert markdown → HTML
6. Update page via REST API with version increment

## Development Commands

### Setup and Installation
```bash
# Create virtual environment and install dependencies
uv sync

# Run the tool
uv run confluence-markdown --help
```

### Testing
```bash
# Run all tests with pytest
uv run pytest

# Run with coverage
uv run pytest --cov=confluence_markdown

# Run specific test
uv run pytest tests/test_main.py::test_url_parsing -v
```

### Running the Tool
```bash
# Direct execution during development
uv run python -m confluence_markdown.main --help

# Test authentication
uv run confluence-markdown --base-url https://confluence.example.com \
  --username USER --token TOKEN --action test-auth
```

## Key Implementation Details

### Page Update Mechanism

When updating pages (`add_content_to_page()` at `main.py:204`), the version number must be incremented:
```python
'version': {'number': page_data['version']['number'] + 1}
```
Missing this causes API rejection. The entire page content must be sent, not just deltas.

### Configuration Security

Config files use restrictive permissions:
- Config directory: `0o700` (user-only access)
- Config file: `0o600` (user read/write only)

Set in `ConfigManager.ensure_config_dir()` (`main.py:439`) and `save_config()` (`main.py:452`).

### Debug Output

The client includes extensive debug logging for troubleshooting:
- URL parsing details (`main.py:259-284`)
- Authentication method used (`main.py:53,56,63`)
- API request/response details (`main.py:118-126`)

All debug output goes to stdout with `DEBUG:` prefix.

### Editor Detection

Editor priority order (`_get_editor()` at `main.py:407`):
1. `$EDITOR` environment variable
2. Common editors: code, vim, nano, emacs, gedit, notepad++
3. Platform fallbacks: notepad (Windows) or vi (Unix)

Uses `shutil.which()` to verify editor availability.

## Testing Notes

Tests use pytest and cover:
- URL parsing for different Confluence URL formats (`test_main.py:15`)
- Client initialization with various auth methods (`test_main.py:33-63`)
- ConfigManager initialization (`test_main.py:8`)

Tests do NOT make actual API calls - they test parsing and initialization logic only.

## Common Pitfalls

1. **Markdown table conversion**: Tables in markdown must use the `tables` extension to convert properly to Confluence HTML. This was fixed in commit `94a654e`.

2. **Page version mismatch**: When updating pages, always fetch current version first and increment by 1. Stale versions cause API errors.

3. **Authentication confusion**: Confluence DC uses different auth than Cloud. For DC 7.9+, use `--username USERNAME --token PAT` (both required).

4. **URL formats**: The tool handles multiple URL formats, but pageId must be extractable either from query params or path segments.

5. **Editor exit codes**: The interactive edit mode checks both file modification time AND editor exit code. Non-zero exit cancels upload.

## Configuration File Structure

`~/.config/confluence-markdown/config.json`:
```json
{
  "default": {
    "base_url": "https://confluence.example.com",
    "username": "user",
    "token": "token_or_password"
  },
  "work": {
    "base_url": "https://work.confluence.com",
    "username": "work-user",
    "token": "work-token"
  }
}
```

Profiles are selected with `--profile NAME`. Default profile is "default".

## Dependencies

- **requests** - HTTP client for REST API calls
- **markdownify** - HTML to Markdown conversion
- **beautifulsoup4** - HTML parsing
- **markdown** - Markdown to HTML conversion with extensions

All dependencies managed via `pyproject.toml` with uv package manager.
