"""MCP stdio server exposing Confluence operations as tools.

Tool families
─────────────
*_storage (RECOMMENDED for agents): use the Confluence storage format
    (XHTML) — Atlassian's native page format — and preserve tables
    (colspan/rowspan), macros (ac: elements), and layouts losslessly.
    Equivalent to ``representation: "storage"`` in the REST API.

*_md: convert content to/from Markdown for human readability.  Convenient
    but lossy for tables with colspan/rowspan and Confluence macros.  Prefer
    the *_storage variants unless you specifically need Markdown output.

Navigation / search tools (search_pages, list_recent_pages, list_spaces,
list_children) have no format dimension and are left unsuffixed.

BREAKING CHANGE from the previous release: the tools formerly named
``get_page``, ``edit_page``, ``create_page``, and ``add_content_to_page``
have been renamed with the ``_md`` suffix.  Update any MCP configurations
that reference the old names.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import contextmanager
from typing import Any

try:
    from mcp.server.elicitation import (
        AcceptedElicitation,
        CancelledElicitation,
        DeclinedElicitation,
    )
    from mcp.server.fastmcp import Context, FastMCP
    from mcp.types import ClientCapabilities, ElicitationCapability, ToolAnnotations
except ImportError as exc:
    raise SystemExit(
        "The 'mcp' extra is required: uv pip install -e '.[mcp]'"
    ) from exc

from pydantic import BaseModel, Field

from .client import ConfluenceClient
from .config import ConfigManager
from .exceptions import ConfigurationError, ConfluenceError

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "confluence",
    instructions=(
        "Read and write Confluence Data Center pages.\n\n"
        "IMPORTANT — tool selection:\n"
        "• Prefer the *_storage tools for all content operations. They use the "
        "Confluence storage format (XHTML) — Atlassian's official native page "
        "format — and preserve tables (colspan/rowspan), macros (ac: elements), "
        "and layouts losslessly. This is equivalent to representation:\"storage\" "
        "in the Confluence REST API.\n"
        "• Use the *_md tools only when you specifically need human-readable "
        "Markdown output (e.g. when summarising a page for a user).\n"
        "• Navigation / search tools have no format dimension: search_pages, "
        "list_recent_pages, list_spaces, list_children."
    ),
)

_client: ConfluenceClient | None = None
_writes_confirmed_session: bool = False


class WriteConfirmation(BaseModel):
    """Schema for human-in-the-loop confirmation of write operations."""

    confirm: bool = Field(description="Confirm the write operation.")
    remember: bool = Field(default=False, description="Skip confirmation for the rest of this session.")


async def _confirm_write(ctx: Context, summary: str) -> None:
    """Ask the user to confirm a destructive write operation via MCP elicitation.

    If the client does not support elicitation the write proceeds without
    confirmation — protection is opportunistic, not a hard gate.
    Raises PermissionError only when a human explicitly declines or cancels.
    """
    global _writes_confirmed_session
    if _writes_confirmed_session:
        return

    if not ctx.session.check_client_capability(
        ClientCapabilities(elicitation=ElicitationCapability())
    ):
        return

    result = await ctx.elicit(
        message=(
            f"This action will modify Confluence content.\n\n"
            f"Operation: {summary}\n\n"
            "Do you want to proceed?"
        ),
        schema=WriteConfirmation,
    )

    match result:
        case AcceptedElicitation(data=data) if data is not None:
            if not data.confirm:
                raise PermissionError("Write operation rejected by user.")
            if data.remember:
                _writes_confirmed_session = True
        case DeclinedElicitation() | CancelledElicitation():
            raise PermissionError("Write operation was declined or cancelled.")
        case _:
            raise PermissionError("Unexpected elicitation result; write blocked.")


def _get_client() -> ConfluenceClient:
    global _client
    if _client is not None:
        return _client

    base_url = os.environ.get("CONFLUENCE_URL")
    username = os.environ.get("CONFLUENCE_USERNAME")
    token = os.environ.get("CONFLUENCE_TOKEN")
    password = os.environ.get("CONFLUENCE_PASSWORD")
    profile = os.environ.get("CONFLUENCE_PROFILE", "default")

    cfg = ConfigManager().load_config(profile)
    if cfg:
        base_url = base_url or cfg.get("base_url")
        username = username or cfg.get("username")
        token = token or cfg.get("token")
        password = password or cfg.get("password")

    if not base_url:
        raise ConfigurationError(
            "No base_url found. Set CONFLUENCE_URL or run "
            "'confluence-markdown --save-config'."
        )
    if not (token or (username and password)):
        raise ConfigurationError(
            "No credentials found. Set CONFLUENCE_TOKEN or run "
            "'confluence-markdown --save-config'."
        )

    _client = ConfluenceClient(
        base_url=base_url,
        username=username,
        password=password,
        token=token,
        verbose=False,
        cache_enabled=True,
        cache_ttl=3600,
    )
    return _client


@contextmanager
def _silence_stdout():
    """Redirect stdout to stderr during calls that print() to stdout."""
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Diagnostic ───────────────────────────────────────────────────────────────


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def check_elicitation_support(ctx: Context) -> str:
    """Return whether the connected MCP client supports elicitation.

    Use this to verify that human-in-the-loop confirmation for write tools
    will be triggered. If elicitation_supported is false, write tools proceed
    without prompting.
    """
    supported = ctx.session.check_client_capability(
        ClientCapabilities(elicitation=ElicitationCapability())
    )
    return _ok({"elicitation_supported": supported})


# ── Navigation / search tools (no format dimension) ───────────────────────────


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def search_pages(
    cql: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> str:
    """Search Confluence pages.

    Provide either a CQL expression (cql) or a plain free-text query (query), but not both.

    Examples:
      cql="space = DEV AND label = important"
      query="kubernetes deployment guide"

    Returns a JSON array of matching pages with id, title, space, url, and a short excerpt.
    """
    if not cql and not query:
        raise ValueError("Provide either 'cql' (CQL expression) or 'query' (free-text search).")
    client = _get_client()
    if not cql:
        cql = client._build_text_search_cql(query)
    limit = max(1, min(limit, 50))
    try:
        results = client.search_pages(cql, limit)
        return _ok(results)
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def list_recent_pages(limit: int = 10) -> str:
    """List Confluence pages recently modified by the authenticated user.

    Returns up to `limit` pages (max 50), sorted by last-modified date descending.
    Each entry includes id, title, space, url, and last-modified timestamp.
    """
    client = _get_client()
    limit = max(1, min(limit, 50))
    try:
        results = client.list_recent_pages(limit)
        return _ok(results)
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def list_spaces(limit: int = 50) -> str:
    """List all Confluence spaces accessible by the authenticated user.

    Returns up to `limit` spaces (max 50). Each entry includes key, name, type, and url.
    Use the space key (e.g. "DEV", "DOCS") when creating pages with create_page_md or
    create_page_storage.
    """
    client = _get_client()
    try:
        results = client.list_spaces(limit)
        return _ok(results)
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def list_children(page_url: str, limit: int = 50) -> str:
    """List the direct child pages of a Confluence page.

    Returns up to `limit` children (max 200). Each entry includes id, title, and url.
    Useful for navigating page hierarchies before reading or editing a specific child.
    """
    client = _get_client()
    limit = max(1, min(limit, 200))
    try:
        results = client.list_children(page_url, limit)
        return _ok(results)
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e


# ── *_storage read/write tools (RECOMMENDED) ─────────────────────────────────


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def get_page_storage(page_url: str) -> str:
    """RECOMMENDED — Get the raw Confluence storage format (XHTML) of a page.

    Returns the page body in Confluence storage format (XHTML) — Atlassian's
    official native page format (``representation: "storage"`` in the REST API).
    This is a lossless representation: tables with colspan/rowspan, macros
    (ac: elements), layouts, and all other Confluence-specific constructs are
    preserved verbatim.

    Use this tool (and the other *_storage tools) whenever you intend to edit
    or analyse page content — it is the preferred tool family for agents.

    Accepts any Confluence page URL, e.g.
      https://wiki.example.com/pages/viewpage.action?pageId=12345
      https://wiki.example.com/display/SPACE/Page+Title

    Returns a JSON object with: id, title, space, version, url, and
    ``storage_content`` (pretty-printed storage XHTML ready for editing).
    """
    client = _get_client()
    try:
        result = client.read_page_content(page_url)
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e
    return _ok({
        "id": result["id"],
        "title": result["title"],
        "space": result["space"],
        "space_key": result["space_key"],
        "version": result["version"],
        "url": result["url"],
        "storage_content": client._prettify_storage(result["html_content"]),
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def edit_page_storage(page_url: str, content: str, ctx: Context) -> str:
    """RECOMMENDED — Replace the full body of a Confluence page with storage format (XHTML).

    Accepts content in Confluence storage format (XHTML) — Atlassian's official
    native page format — and uploads it losslessly via ``representation: "storage"``.
    Tables with colspan/rowspan, macros (ac: elements), layouts, and all other
    Confluence constructs are preserved exactly.

    The content is validated for well-formedness before upload; malformed XHTML
    is rejected locally with a clear error message (no opaque HTTP 400).

    Use get_page_storage first to read the current storage content, then supply
    the modified XHTML here.

    Prefer this tool over edit_page_md for any page that contains tables, macros,
    or complex layouts.  Use edit_page_md only when you specifically need to supply
    Markdown input.

    Returns a JSON object with the page's id, title, new version number, and url.
    """
    await _confirm_write(ctx, f"Overwrite full content of page at {page_url} (storage format)")
    client = _get_client()
    ok, err = client._validate_storage_xhtml(content)
    if not ok:
        raise ValueError(f"Invalid Confluence storage format XHTML: {err}")
    with _silence_stdout():
        try:
            result = client.edit_page_with_editor(
                page_url, content=content, content_type="storage"
            )
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e
    page_id = result["id"]
    return _ok({
        "id": page_id,
        "title": result.get("title"),
        "version": result.get("version", {}).get("number"),
        "url": f"{client.base_url}/pages/viewpage.action?pageId={page_id}",
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def create_page_storage(
    space_key: str,
    title: str,
    content: str,
    ctx: Context,
    parent_id: str | None = None,
) -> str:
    """RECOMMENDED — Create a new Confluence page with storage format (XHTML) content.

    Accepts the page body in Confluence storage format (XHTML) — Atlassian's
    official native page format — and creates the page losslessly.  Tables,
    macros, layouts, and all Confluence-specific constructs are preserved.

    The content is validated for well-formedness before upload.

    Args:
        space_key: Key of the target space (e.g. "DEV", "DOCS"). Use list_spaces to find it.
        title: Page title (must be unique within the space).
        content: Page body in Confluence storage format (XHTML).
        parent_id: Optional numeric ID of the parent page.

    Prefer this tool over create_page_md when the page content contains tables,
    macros, or complex layouts.

    Returns a JSON object with the new page's id, title, and url.
    """
    await _confirm_write(ctx, f"Create page '{title}' in space '{space_key}' (storage format)")
    client = _get_client()
    ok, err = client._validate_storage_xhtml(content)
    if not ok:
        raise ValueError(f"Invalid Confluence storage format XHTML: {err}")
    with _silence_stdout():
        try:
            result = client.create_page(
                space_key=space_key,
                title=title,
                content=content,
                parent_id=parent_id,
                content_type="html",
            )
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e
    page_id = result["id"]
    return _ok({
        "id": page_id,
        "title": result.get("title", title),
        "url": f"{client.base_url}/pages/viewpage.action?pageId={page_id}",
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def add_content_storage(
    page_url: str,
    content: str,
    ctx: Context,
    append: bool = True,
) -> str:
    """RECOMMENDED — Add storage format (XHTML) content to an existing Confluence page.

    Appends or prepends content in Confluence storage format (XHTML) —
    Atlassian's official native page format — without replacing the existing
    body.  Tables, macros, and layouts are preserved losslessly.

    The supplied content is validated for well-formedness before upload.

    Args:
        page_url: URL of the page to update.
        content: Content to add in Confluence storage format (XHTML).
        append: True (default) to add after existing content; False to prepend.

    Prefer this tool over add_content_md when adding content with tables or macros.

    Returns a JSON object with the page's id, title, and new version number.
    """
    client = _get_client()
    ok, err = client._validate_storage_xhtml(content)
    if not ok:
        raise ValueError(f"Invalid Confluence storage format XHTML: {err}")
    position = "append to" if append else "prepend to"
    await _confirm_write(ctx, f"Add storage content ({position}) page at {page_url}")
    try:
        result = client.add_content_to_page(
            page_url, content, append=append, content_type="html"
        )
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e
    return _ok({
        "id": result["id"],
        "title": result.get("title"),
        "version": result.get("version", {}).get("number"),
    })


# ── *_md read/write tools ─────────────────────────────────────────────────────


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def get_page_md(page_url: str) -> str:
    """Get the content of a Confluence page converted to Markdown.

    Convenient for human-readable summaries, but lossy: tables with
    colspan/rowspan, macros (ac: elements), and complex layouts cannot be
    faithfully represented in Markdown.  Prefer get_page_storage when you
    intend to edit or re-upload the content.

    Accepts any Confluence page URL, e.g.
      https://wiki.example.com/pages/viewpage.action?pageId=12345
      https://wiki.example.com/display/SPACE/Page+Title

    Returns a JSON object with: id, title, space, version, url, and the page
    body converted to Markdown.
    """
    client = _get_client()
    try:
        result = client.read_page_content(page_url)
        return _ok(result)
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def edit_page_md(page_url: str, content: str, ctx: Context) -> str:
    """Replace the full body of a Confluence page with Markdown content.

    Convenient for simple pages, but lossy for tables with colspan/rowspan,
    macros (ac: elements), and complex layouts.  Prefer edit_page_storage for
    any page that contains such constructs.

    The existing page content is completely overwritten.  Use add_content_md
    if you only want to append or prepend without discarding the current body.

    Returns a JSON object with the page's id, title, new version number, and url.
    """
    await _confirm_write(ctx, f"Overwrite full content of page at {page_url}")
    client = _get_client()
    with _silence_stdout():
        try:
            result = client.edit_page_with_editor(
                page_url, content=content, content_type="markdown"
            )
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e
    page_id = result["id"]
    return _ok({
        "id": page_id,
        "title": result.get("title"),
        "version": result.get("version", {}).get("number"),
        "url": f"{client.base_url}/pages/viewpage.action?pageId={page_id}",
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def create_page_md(
    space_key: str,
    title: str,
    content: str,
    ctx: Context,
    parent_id: str | None = None,
) -> str:
    """Create a new Confluence page with Markdown content.

    Convenient for simple pages, but lossy for tables with colspan/rowspan,
    macros, and complex layouts.  Prefer create_page_storage for pages that
    contain such constructs.

    Args:
        space_key: Key of the target space (e.g. "DEV", "DOCS"). Use list_spaces to find it.
        title: Page title (must be unique within the space).
        content: Page body in Markdown format.
        parent_id: Optional numeric ID of the parent page.

    Returns a JSON object with the new page's id, title, and url.
    """
    await _confirm_write(ctx, f"Create page '{title}' in space '{space_key}'")
    client = _get_client()
    with _silence_stdout():
        try:
            result = client.create_page(
                space_key=space_key,
                title=title,
                content=content,
                parent_id=parent_id,
                content_type="markdown",
            )
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e
    page_id = result["id"]
    return _ok({
        "id": page_id,
        "title": result.get("title", title),
        "url": f"{client.base_url}/pages/viewpage.action?pageId={page_id}",
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def add_content_md(
    page_url: str,
    content: str,
    ctx: Context,
    append: bool = True,
) -> str:
    """Add Markdown content to an existing Confluence page without replacing it.

    Convenient for simple content, but lossy for tables with colspan/rowspan,
    macros, and complex layouts.  Prefer add_content_storage for such cases.

    Args:
        page_url: URL of the page to update.
        content: Markdown content to add.
        append: True (default) to add after existing content; False to prepend before it.

    Returns a JSON object with the page's id, title, and new version number.
    """
    position = "append to" if append else "prepend to"
    await _confirm_write(ctx, f"Add content ({position}) page at {page_url}")
    client = _get_client()
    try:
        result = client.add_content_to_page(
            page_url, content, append=append, content_type="markdown"
        )
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e
    return _ok({
        "id": result["id"],
        "title": result.get("title"),
        "version": result.get("version", {}).get("number"),
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def move_page(page_url: str, new_parent_id: str, ctx: Context) -> str:
    """Move a Confluence page to a new parent (change its position in the hierarchy).

    Changes which page a page appears under in the Confluence page tree.
    Does not modify the page's content, only its parent.

    Args:
        page_url: URL or ID of the page to move.
        new_parent_id: ID of the target parent page.

    Returns a JSON object with the moved page's id, title, and url.
    """
    client = _get_client()
    page_id = client._extract_page_id_from_url(page_url)
    if not page_id:
        raise ValueError(f"Could not extract page ID from URL: {page_url}")

    # Get page info for confirmation
    page_data = client.get_page_content(page_id)
    page_title = page_data.get("title", page_id)

    await _confirm_write(
        ctx,
        f"Move page '{page_title}' to parent ID {new_parent_id}"
    )

    with _silence_stdout():
        try:
            result = client.move_page(page_id, new_parent_id)
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e

    return _ok({
        "id": result["id"],
        "title": result.get("title"),
        "url": f"{client.base_url}/pages/viewpage.action?pageId={result['id']}",
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_page(page_url: str, ctx: Context) -> str:
    """Delete a Confluence page (move it to trash).

    The page can be recovered from trash within a retention period (typically 30 days).
    If the page has child pages, the children are NOT deleted — they become
    top-level pages in their respective spaces.

    Args:
        page_url: URL or ID of the page to delete.

    Returns a JSON object with the deleted page's id and title.
    """
    client = _get_client()
    page_id = client._extract_page_id_from_url(page_url)
    if not page_id:
        raise ValueError(f"Could not extract page ID from URL: {page_url}")

    # Get page info for confirmation warning
    page_data = client.get_page_content(page_id)
    page_title = page_data.get("title", page_id)

    # Count children for warning
    try:
        children = client.list_children(page_url, limit=999)
        num_children = len(children) if children else 0
    except Exception:
        num_children = 0

    warning = f"Delete page '{page_title}'"
    if num_children > 0:
        warning += f" (has {num_children} child page(s) — they will become top-level)"

    await _confirm_write(ctx, warning)

    with _silence_stdout():
        try:
            client.delete_page(page_id)
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e

    return _ok({
        "id": page_id,
        "title": page_title,
        "status": "deleted (in trash)",
    })


# ── Attachment tools ──────────────────────────────────────────────────────────


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def list_attachments(page_url: str, limit: int = 50) -> str:
    """List the attachments of a Confluence page.

    Returns up to `limit` attachments (max 200). Each entry includes id, title
    (filename), media_type, file_size in bytes, version, and download_url.

    Args:
        page_url: URL or ID of the page.
        limit: Maximum number of attachments to return.
    """
    client = _get_client()
    page_id = client._extract_page_id_from_url(page_url)
    if not page_id:
        raise ValueError(f"Could not extract page ID from URL: {page_url}")
    limit = max(1, min(limit, 200))
    try:
        results = client.list_attachments(page_id, limit)
        return _ok(results)
    except ConfluenceError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def download_attachment(page_url: str, filename: str, output_path: str) -> str:
    """Download an attachment from a Confluence page to a local file.

    Use list_attachments first to see available filenames.

    Args:
        page_url: URL or ID of the page.
        filename: Name of the attachment as returned by list_attachments.
        output_path: Local file path or directory to save the attachment to.

    Returns a JSON object with the saved file path and size in bytes.
    """
    client = _get_client()
    page_id = client._extract_page_id_from_url(page_url)
    if not page_id:
        raise ValueError(f"Could not extract page ID from URL: {page_url}")
    with _silence_stdout():
        try:
            saved = client.download_attachment(page_id, filename, output_path)
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e
    return _ok({
        "path": saved,
        "size": os.path.getsize(saved),
    })


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def upload_attachment(
    page_url: str, file_path: str, ctx: Context, comment: str = ""
) -> str:
    """Upload a local file as an attachment to a Confluence page.

    If an attachment with the same filename already exists on the page,
    a new version of that attachment is created (the old version remains
    in the attachment history).

    Args:
        page_url: URL or ID of the target page.
        file_path: Local path of the file to upload.
        comment: Optional version comment for the attachment.

    Returns a JSON object with the attachment's id, title, version, and download_url.
    """
    client = _get_client()
    page_id = client._extract_page_id_from_url(page_url)
    if not page_id:
        raise ValueError(f"Could not extract page ID from URL: {page_url}")
    if not os.path.isfile(file_path):
        raise ValueError(f"File not found: {file_path}")

    page_data = client.get_page_content(page_id)
    page_title = page_data.get("title", page_id)
    filename = os.path.basename(file_path)

    await _confirm_write(
        ctx,
        f"Upload attachment '{filename}' to page '{page_title}'"
    )

    with _silence_stdout():
        try:
            result = client.upload_attachment(page_id, file_path, comment)
        except ConfluenceError as e:
            raise RuntimeError(str(e)) from e

    return _ok(result)


# ── MCP Resources ─────────────────────────────────────────────────────────────


@mcp.resource("confluence://page/{page_id}")
def page_resource(page_id: str) -> str:
    """Return a Confluence page as a Markdown MCP resource.

    Access via URI: confluence://page/{page_id}
    The page body is converted from Confluence storage format to Markdown.
    For lossless access use the storage variant: confluence://page/{page_id}/storage
    """
    client = _get_client()
    try:
        data = client.get_page_content(page_id)
    except Exception as e:
        raise RuntimeError(f"Could not load page {page_id}: {e}") from e
    html = data["body"]["storage"]["value"]
    md = client._html_to_markdown(html)
    title = data.get("title", page_id)
    return f"# {title}\n\n{md}"


@mcp.resource("confluence://page/{page_id}/storage")
def page_resource_storage(page_id: str) -> str:
    """Return a Confluence page as a storage format (XHTML) MCP resource.

    Access via URI: confluence://page/{page_id}/storage
    Returns the raw Confluence storage format (XHTML) — Atlassian's official
    native page format — pretty-printed for readability.  Tables, macros, and
    layouts are preserved losslessly.
    For Markdown access use: confluence://page/{page_id}
    """
    client = _get_client()
    try:
        data = client.get_page_content(page_id)
    except Exception as e:
        raise RuntimeError(f"Could not load page {page_id}: {e}") from e
    html = data["body"]["storage"]["value"]
    title = data.get("title", page_id)
    pretty = client._prettify_storage(html)
    return f"<!-- Title: {title} -->\n{pretty}"


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
