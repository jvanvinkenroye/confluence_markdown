# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-01-24

### Added - Pagination Support
- **Automatic pagination** for fetching ALL spaces and pages from Confluence API
- Progress indicators when fetching large datasets (e.g., "Fetched 100 pages so far...")
- Complete data visibility for instances with 100+ spaces or 1000+ pages
- New `PAGINATION.md` documentation explaining technical implementation

### Changed
- `confluence-fzf.sh` now fetches ALL pages using pagination loop (previously limited to ~100-200)
- `confluence-create.sh` now fetches ALL spaces and pages using pagination (previously limited to 100)
- Both scripts make multiple API calls as needed to retrieve complete datasets
- API limit changed from 1000 to 100 per request for better compatibility

### Fixed
- **Critical bug**: Scripts were only showing first 100 spaces or ~200 pages
- Missing pages/spaces in large Confluence instances now fully accessible
- Confluence REST API pagination properly handled

### Performance
- Small instances (<100 items): 1 API call (no change)
- Medium instances (100-500): 2-5 API calls (1-2 seconds)
- Large instances (1000+): 10+ API calls (few seconds)

## [1.2.0] - 2025-01-23

### Added - Script Unification
- **Unified scripts** with automatic fzf detection
- Both `confluence-create.sh` and `confluence-fzf.sh` now work with OR without fzf
- Automatic fallback to bash `select` menu mode when fzf is not available
- Clear mode indication: "(fzf mode)" or "(menu mode)"
- Helpful tips suggesting fzf installation when in menu mode
- New `UNIFIED.md` documentation

### Changed
- `confluence-create.sh` - Unified version with auto-detection
- `confluence-fzf.sh` - Unified version with auto-detection
- Both scripts now use `HAS_FZF` variable to detect fzf availability

### Deprecated
- `confluence-create-simple.sh` - Functionality merged into main script
- `confluence-create-fzf-only.sh.backup` - Replaced by unified version
- `confluence-new.sh` - No longer needed with auto-detection
- `confluence-fzf-backup.sh` - Replaced by unified version
- `confluence-fzf-original.sh.backup` - Replaced by unified version

### Removed
- Legacy scripts moved to `legacy/` folder with README explaining migration

## [1.1.0] - 2025-01-22

### Added - Interactive Scripts
- **confluence-fzf.sh** - Interactive page selector with fzf for editing/reading existing pages
- **confluence-create.sh** - Interactive page creation wizard with space/parent selection
- Three page templates:
  - `templates/meeting-notes.md` - Meeting notes template with action items table
  - `templates/project-plan.md` - Project planning template
  - `templates/documentation.md` - Technical documentation template
- Enhanced output formatting showing page URL after operations
- New documentation files:
  - `CREATE_PAGES.md` - Page creation guide
  - `FZF_WORKFLOW.md` - Interactive workflow documentation
  - `ALTERNATIVES.md` - Non-fzf alternatives guide

### Changed
- Scripts now display formatted success messages with page URLs
- Improved user experience with colored output and clear section separators

## [1.0.0] - 2025-01-21

### Added - Page Creation
- **Page creation capability** via `--action create`
- New CLI arguments: `--space`, `--title`, `--parent-id`, `--content`
- `create_page()` method in ConfluenceClient class
- Support for creating pages with parent hierarchy
- Automatic markdown to HTML conversion for new pages
- Page creation examples in README.md

### Fixed
- **Table rendering** - Fixed markdown tables not converting to Confluence HTML (commit 94a654e)
  - Added `tables` extension to Python markdown library
  - Tables now properly render in Confluence

## [0.2.0] - 2025-01-20

### Added - Documentation and Testing
- **CLAUDE.md** - Comprehensive architecture documentation for AI assistance
- **CONTENT_TYPES.md** - Complete reference for supported markdown/HTML features
- **TODO.md** - Development roadmap with 60+ actionable items
- Test coverage reporting (22% initial coverage)

### Fixed
- Identified critical security issue: tokens printed in debug output (documented in TODO)
- Documented error handling gaps and missing timeout configuration

### Changed
- Updated `.gitignore` to exclude:
  - Coverage reports (.coverage, htmlcov/)
  - Test files (test-*.md)
  - IDE directories (.vscode/, .idea/)
  - Editor backups (*~, *.swp)
  - .claude/ directory

## [0.1.0] - Initial Release

### Added
- Download Confluence pages as markdown
- Read page content in terminal
- Add content to existing pages (markdown or HTML)
- Interactive editing with local text editors
- Multiple authentication methods:
  - Personal Access Token (PAT) with username
  - Bearer token
  - Username/password
- Configuration file support (~/.config/confluence-markdown/config.json)
- Multiple profile support
- Debug mode for troubleshooting
- Support for various content types:
  - Headings, lists, tables
  - Code blocks (inline and fenced)
  - Bold, italic, combined formatting
  - Links, blockquotes
  - External images

### Technical Details
- Python-based CLI tool using requests, markdownify, beautifulsoup4, markdown
- Bidirectional HTML ↔ Markdown conversion
- Secure config file permissions (0o600)
- Multiple Confluence URL format parsing
- Page version management for updates

---

## Release Notes

### v2.0.0 - Breaking Changes
- None. Pagination is backward compatible.

### v1.2.0 - Breaking Changes
- None. Scripts work with existing workflows.
- Users of deprecated scripts in `legacy/` folder should migrate to unified versions.

### Migration Guide
See `legacy/README.md` for migration instructions from older script versions.

## Links
- [PAGINATION.md](PAGINATION.md) - Pagination technical documentation
- [UNIFIED.md](UNIFIED.md) - Script unification guide
- [CLAUDE.md](CLAUDE.md) - Architecture overview
- [CONTENT_TYPES.md](CONTENT_TYPES.md) - Supported content types
- [CREATE_PAGES.md](CREATE_PAGES.md) - Page creation guide
- [FZF_WORKFLOW.md](FZF_WORKFLOW.md) - Interactive workflows
- [TODO.md](TODO.md) - Development roadmap
