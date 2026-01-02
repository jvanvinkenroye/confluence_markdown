# TODO List - Confluence Markdown Tool

Generated from code analysis on 2025-10-23

## Critical Issues (High Priority)

### Security

- [ ] **Remove sensitive data from debug output** (main.py:53,56,63)
  - Tokens and passwords are printed in debug mode
  - Implement secrets masking for all authentication output
  - Use logging module with proper log levels

- [ ] **Add request timeout configuration** (main.py:122)
  - HTTP requests have no timeout, can hang indefinitely
  - Add configurable timeout (default 30s)
  - Implement retry logic with exponential backoff

- [ ] **Validate URLs before API calls** (main.py:257)
  - No validation that URLs are from expected Confluence domain
  - Could be used to make requests to arbitrary hosts
  - Add URL allowlist or domain validation

- [ ] **Sanitize error messages**
  - Error messages may leak sensitive information
  - Mask tokens/passwords in exception messages
  - Review all print(f"ERROR: {response.text}") statements

### Error Handling

- [ ] **Add validation for page URL format** (main.py:97-99)
  - `_extract_page_id_from_url()` can return None
  - Only raises ValueError after None is returned
  - Should validate URL format before attempting extraction

- [ ] **Handle editor subprocess failures** (main.py:343)
  - Only checks return code, not all failure modes
  - Add timeout for editor subprocess
  - Handle cases where editor doesn't exist or can't be executed

- [ ] **Validate markdown/HTML conversion**
  - No error handling if markdownify or markdown libraries fail
  - Large documents could cause memory issues
  - Add size limits and error recovery

- [ ] **Handle network failures gracefully**
  - No retry logic for transient network errors
  - No handling of connection timeouts
  - Add exponential backoff for 429 (rate limit) responses

## Testing (High Priority)

### Test Coverage (Currently 22%)

- [ ] **Add unit tests for ConfluenceClient methods**
  - [ ] Test `get_page_content()` with mocked responses
  - [ ] Test `download_as_markdown()` with various HTML inputs
  - [ ] Test `add_content_to_page()` with append/prepend
  - [ ] Test `edit_page_with_editor()` (mock subprocess)
  - [ ] Test error conditions (404, 401, 500 responses)

- [ ] **Add tests for ConfigManager**
  - [ ] Test `save_config()` creates proper file permissions
  - [ ] Test `load_config()` handles missing files
  - [ ] Test `delete_profile()` removes correct profile
  - [ ] Test multiple profile management
  - [ ] Test config file corruption handling

- [ ] **Add tests for HTML/Markdown conversion**
  - [ ] Test tables (regression test for commit 94a654e)
  - [ ] Test code blocks (fenced and indented)
  - [ ] Test nested lists
  - [ ] Test special characters and escaping
  - [ ] Test large documents

- [ ] **Add integration tests**
  - [ ] Test against mock Confluence server
  - [ ] Test full workflow: download → edit → upload
  - [ ] Test authentication methods (PAT, username/password)
  - [ ] Test config file operations end-to-end

- [ ] **Add edge case tests**
  - [ ] Empty page content
  - [ ] Very large pages (>10MB)
  - [ ] Pages with special characters in title
  - [ ] Invalid page IDs
  - [ ] Expired tokens/credentials

## Code Quality (Medium Priority)

### Replace print() with logging module

- [ ] **Implement proper logging** (throughout main.py)
  - Replace all print() statements with logging
  - Create logger with proper hierarchy
  - Add --verbose and --quiet flags
  - Separate debug, info, warning, error levels
  - Log to file option for troubleshooting

### Refactoring

- [ ] **Split main.py into modules**
  - main.py is 687 lines, should be split
  - Create `client.py` for ConfluenceClient
  - Create `config.py` for ConfigManager
  - Create `converters.py` for HTML/Markdown utilities
  - Create `cli.py` for argparse and main()
  - Keep main.py as entry point only

- [ ] **Reduce function complexity**
  - `edit_page_with_editor()` is 96 lines (main.py:309-405)
  - `main()` is 187 lines (main.py:497-684)
  - Extract helper functions for complex logic
  - Apply single responsibility principle

- [ ] **Remove code duplication**
  - Version increment logic repeated in multiple places
  - API request pattern repeated (could be a helper method)
  - Error handling patterns repeated

### Type Hints

- [ ] **Add missing type hints**
  - Some function parameters lack type hints
  - Add return type hints to all functions
  - Use `typing.Optional` consistently
  - Consider using `TypedDict` for API responses

### Documentation

- [ ] **Add docstring examples**
  - Include usage examples in docstrings
  - Document expected exceptions
  - Add parameter validation notes

- [ ] **Document API response formats**
  - Add examples of Confluence API responses
  - Document what fields are used from responses
  - Note any version-specific differences

## Features & Improvements (Low Priority)

### Safety Features

- [ ] **Add dry-run mode**
  - Show what would change without making changes
  - Useful for `--action add` and `--action edit`
  - Add `--dry-run` flag

- [ ] **Add backup before edit**
  - Save original content before modifications
  - Allow restore if something goes wrong
  - Store in `~/.cache/confluence-markdown/backups/`

- [ ] **Show diff before upload**
  - Display changes that will be made
  - Require confirmation for destructive operations
  - Use difflib or external diff tool

### User Experience

- [ ] **Add progress indicators**
  - Show progress for long-running operations
  - Use tqdm or similar for downloads
  - Spinner for API calls

- [ ] **Better error messages**
  - More helpful messages for common errors
  - Suggestions for fixing issues
  - Link to documentation for authentication problems

- [ ] **Interactive mode improvements**
  - Prompt for missing required arguments
  - Offer to save config after successful auth
  - Better editor detection and configuration

### Additional Features

- [ ] **Support for attachments**
  - Download attachments with page
  - Upload attachments to pages
  - List attachments on a page

- [ ] **Batch operations**
  - Download multiple pages at once
  - Update multiple pages with same content
  - Export entire space to markdown

- [ ] **Search functionality**
  - Search pages by title or content
  - List pages in a space
  - Find pages by label

- [ ] **Version history**
  - View page history
  - Compare versions
  - Restore previous versions

- [ ] **Templates**
  - Create pages from markdown templates
  - Save page as template
  - Template variable substitution

## Build & Deployment

### Package Configuration

- [ ] **Fix deprecation warning**
  - `tool.uv.dev-dependencies` is deprecated
  - Migrate to `dependency-groups.dev` in pyproject.toml
  - Update uv to latest version

### CI/CD

- [ ] **Set up GitHub Actions**
  - Run tests on push/PR
  - Check code coverage
  - Run linting (ruff)
  - Type checking (mypy)

- [ ] **Add pre-commit hooks**
  - Run tests before commit
  - Format code with ruff
  - Check for secrets in code

### Documentation

- [ ] **Create CONTRIBUTING.md**
  - Development setup instructions
  - How to run tests
  - Code style guidelines
  - PR process

- [ ] **Add examples directory**
  - Example scripts for common workflows
  - Sample config files
  - Integration examples

- [ ] **Create changelog**
  - Document changes between versions
  - Follow Keep a Changelog format
  - Note breaking changes

## Performance

- [ ] **Cache API responses**
  - Cache page metadata to reduce API calls
  - Implement TTL for cache entries
  - Use etags for conditional requests

- [ ] **Optimize markdown conversion**
  - Profile conversion performance
  - Stream large documents instead of loading entirely
  - Consider async/parallel processing for batch operations

- [ ] **Connection pooling**
  - Reuse HTTP connections
  - Configure session properly with pool size
  - Add keep-alive support

## Code Analysis Summary

**Statistics:**
- Lines of code: 687 (main.py), 67 (tests)
- Test coverage: 22% (268 lines untested)
- Functions lacking tests: 12 out of 15

**Most Critical Areas:**
1. Security: Sensitive data in debug output, no request timeout
2. Testing: Only 22% coverage, no integration tests
3. Error handling: Many unhandled edge cases
4. Code organization: Single 687-line file, needs modularization

**Quick Wins:**
1. Replace print() with logging module
2. Add request timeouts to all HTTP calls
3. Add tests for URL parsing edge cases
4. Fix pyproject.toml deprecation warning
5. Add basic input validation

**Technical Debt:**
- No CI/CD pipeline
- No pre-commit hooks
- No code coverage requirements
- No integration tests
- Single-file architecture
