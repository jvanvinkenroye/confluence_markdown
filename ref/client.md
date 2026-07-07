# ConfluenceClient reference

`src/confluence_markdown/client.py`

## Constructor

```python
ConfluenceClient(
    base_url: str,
    username: str | None = None,
    password: str | None = None,
    token: str | None = None,
    verbose: bool = False,
    editor: str | None = None,
    table_format: str = "markdown",   # "markdown" | "yaml"
    cache_enabled: bool = True,
    cache_ttl: int = 3600,
)
```

## Public methods

### Auth
| Method | Returns | Notes |
|--------|---------|-------|
| `test_authentication()` | `dict` | GET `/rest/api/user/current` |

### Page lookup
| Method | Returns | Notes |
|--------|---------|-------|
| `get_page_by_url(page_url)` | `dict` | Extract page ID from URL, fetch metadata |
| `get_page_content(page_id)` | `dict` | Fetch page with `body.storage` expansion |
| `read_page_content(page_url)` | `dict` | Full page info + `markdown_content` key |

### Listing / search
| Method | Returns | Notes |
|--------|---------|-------|
| `list_recent_pages(limit=10)` | `list[dict]` | Recently modified via CQL |
| `list_recently_viewed_pages(limit=10, use_cache=True)` | `list[dict]` | Recently viewed via CQL |
| `search_pages(cql, limit=10)` | `list[dict]` | CQL search, paginated |
| `list_children(page_url, limit=50)` | `list[dict]` | Direct children |

### Content modification
| Method | Returns | Notes |
|--------|---------|-------|
| `add_content_to_page(page_url, content, content_type, append)` | `dict` | Append or prepend content |
| `edit_page_with_editor(page_url, content=None, content_type="markdown")` | `dict \| None` | Interactive editor; skip editor if `content` provided |
| `create_page(space_key, title, content, content_type, parent_id)` | `dict` | Create page |
| `create_page_with_editor(space_key, title, parent_url, content)` | `dict \| None` | Create then edit |
| `create_task_page(space_key, title, category, priority, status, parent_id)` | `dict` | Task template |

### Organize / delete
| Method | Returns | Notes |
|--------|---------|-------|
| `move_page(page_id, new_parent_id)` | `dict` | PUT with updated `ancestors`, increments version |
| `delete_page(page_id)` | `bool` | DELETE — page goes to trash (recoverable) |

### Attachments
| Method | Returns | Notes |
|--------|---------|-------|
| `list_attachments(page_id, limit=50)` | `list[dict]` | id, title, media_type, file_size, version, download_url |
| `download_attachment(page_id, filename, output_path)` | `str` | Streams to file; detects SSO login redirects and raises `ConfluenceError` (Kantega SSO: `/download/attachments` must be whitelisted for API tokens) |
| `upload_attachment(page_id, file_path, comment="")` | `dict` | Multipart POST with `X-Atlassian-Token: nocheck`; same filename → new attachment version |

### Download
| Method | Returns | Notes |
|--------|---------|-------|
| `download_as_markdown(page_url, output_path, recursive)` | `Path` | Write markdown file |
| `download_pages_parallel(page_urls)` | `list[tuple[str,str]]` | Batch sync wrapper |

### Async batch (use via sync wrappers)
| Method | Notes |
|--------|-------|
| `async_get_pages_batch(page_ids)` | Parallel page fetches |
| `async_download_pages_batch(page_ids, output_dir)` | Parallel markdown write |
| `async_list_children_recursive(page_id, limit)` | Recursive child walk |
| `list_children_recursive_parallel(page_url)` | Sync wrapper for async recursive |

## HTML ↔ Markdown conversion

| Method | Notes |
|--------|-------|
| `_html_to_markdown(html)` | Main HTML→MD pipeline (calls markdownify + post-process) |
| `_html_to_markdown_with_macros(html, page_id)` | Preserves Confluence macros as fenced blocks |
| `_markdown_to_html(md)` | MD→HTML using `markdown` lib |
| `_convert_tables_to_yaml(md)` | Replace markdown tables with YAML blocks (for editing) |
| `_convert_yaml_to_tables(content)` | Reverse: YAML blocks → markdown tables |

## Pagination helper

`_search_paginated(cql, limit, extra_params)` — fetches up to `limit` results using `start` offset; follows `_links.next` until done.

## Rate limiting

`_handle_rate_limit(response)` — logs warning when < 5 requests remain; sleeps on 429 using `Retry-After` header.

## Retry policy (tenacity)

Applied to `_request()`: exponential backoff, up to 3 attempts, on connection errors and 5xx responses.

## Rendering

| Method | Notes |
|--------|-------|
| `_render_markdown_to_ansi(md, width)` | Rich → ANSI string |
| `_paginate_text(text, show_actions)` | Pipe through `$PAGER` or `less`; returns user action key |
| `_build_rich_renderables(md)` | Build Rich panels for display |

## Key internal helpers

| Method | Notes |
|--------|-------|
| `_extract_page_id_from_url(url)` | Parse `pageId` query param or `/pages/<id>/` path |
| `_extract_space_key_from_url(url)` | Parse `/spaces/<KEY>/` from URL |
| `_redact_headers(headers)` | Mask auth/token headers in debug output |
| `_get_editor()` | Resolve editor: `--editor` → `$EDITOR` → `vi` |
