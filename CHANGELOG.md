# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-02-26

### Added

#### Core Actions
- `read` - Read a specific Confluence page rendered in terminal with Rich
- `read-recent` - Browse recently viewed pages interactively
- `edit` - Edit a page in your preferred editor and push changes back
- `edit-recent` - Select from recently edited pages and edit
- `download` - Download a page as markdown file
- `add` - Append or prepend content (markdown or HTML) to a page
- `create` - Create a new page from content
- `create-edit` - Create a new page via editor
- `create-task` - Create a task page with Page Properties macro
- `search` - Search pages by text query or CQL
- `list-children` - List child pages (optionally recursive)
- `test-auth` - Verify authentication credentials

#### Navigation
- Interactive page selection via fzf (fuzzy finder) with fallback to InquirerPy
- `--no-fzf` flag to force InquirerPy selector

#### Table Support
- Complex tables with colspan/rowspan preserved as HTML during round-trips
- Meeting tables preserved as-is
- `--table-format yaml` option for easier editing of complex tables

#### Configuration
- Config file at `~/.config/confluence-markdown/config.json`
- Multiple named profiles (`--profile`)
- Per-space editor and table-format settings
- `--init-config` to generate an example config
- `--save-config` to persist credentials
- `--list-profiles` / `--delete-profile` management commands

#### Performance
- Response caching with configurable TTL (default: 1 hour)
- Parallel async API calls for batch operations (recursive download, list-children)
- Automatic retry with exponential backoff on rate limit errors

#### Quality of Life
- `--raw` flag for plain markdown output (scripting-friendly)
- `--quiet` / `--verbose` logging modes
- `--recursive` for recursive child page operations
- `--output-dir` for batch downloads
- Shell tab completion via argcomplete (bash/zsh)
- `--version` flag
- `--clear-cache` / `--no-cache` cache management

[0.1.0]: https://github.com/jvanvinkenroye/confluence_markdown/releases/tag/v0.1.0
