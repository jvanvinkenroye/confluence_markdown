# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-06-22

### Added

#### Confluence storage format (XHTML) mode

Support for Confluence **storage format** (Atlassian's official format), the
lossless XHTML representation used by Confluence's REST API
(`representation: "storage"`). Unlike Markdown, storage format is a pure
passthrough: tables with colspan/rowspan, macros (`ac:` elements), layouts,
and all Confluence-specific constructs are preserved exactly.

See the [Confluence storage format documentation](https://confluence.atlassian.com/doc/confluence-storage-format-790796544.html).

**MCP server — new `*_storage` tool family (recommended for agents):**
- `get_page_storage` — returns raw storage XHTML (pretty-printed); use as input for the other storage write tools.
- `edit_page_storage` — replaces page body with storage XHTML; validates well-formedness before upload.
- `create_page_storage` — creates a new page with storage XHTML content.
- `add_content_storage` — appends/prepends storage XHTML to an existing page.

All storage write tools preserve the human-in-the-loop elicitation confirmation.

The MCP server `instructions` now steer agents toward the `*_storage` tools as
the preferred choice for content operations.

**New MCP resource:** `confluence://page/{page_id}/storage` — exposes raw
storage XHTML as an MCP resource.

**CLI:** `--format {md,storage}` flag (default `md`) for `download` and `edit`
actions. `--format storage` downloads/edits pages in Confluence storage format
(XHTML, Atlassian's official format) without any Markdown conversion.

**New helpers in `ConfluenceClient`:**
- `_validate_storage_xhtml(html)` — validates well-formedness, normalises `<br>` and void elements, detects bare `&`; rejects malformed input locally before the API call.
- `_prettify_storage(html)` — pretty-prints storage XHTML while preserving significant whitespace in `<pre>`, `<ac:plain-text-body>`, and `<ac:plain-text-link-body>`.

### Fixed

- `edit_page_with_editor` with `content_type="html"` (non-interactive mode)
  previously converted storage XHTML to Markdown and back (`html→md→html`),
  silently destroying tables and macros. It now validates and uploads the
  storage XHTML directly.

### Breaking Changes

The following MCP tool names have been renamed with a format suffix to make
room for the new `*_storage` variants. Update any MCP client configurations
that reference the old names:

| Old name | New name |
|---|---|
| `get_page` | `get_page_md` |
| `edit_page` | `edit_page_md` |
| `create_page` | `create_page_md` |
| `add_content_to_page` | `add_content_md` |

The old names are fully removed; no aliases are provided.

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
