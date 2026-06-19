"""MCP stdio server exposing Confluence operations as tools."""

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
    instructions="Read and write Confluence Data Center pages",
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


# ── Read tools ────────────────────────────────────────────────────────────────


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
def get_page(page_url: str) -> str:
    """Get the full content of a Confluence page by its URL.

    Accepts any Confluence page URL, e.g.
      https://wiki.example.com/pages/viewpage.action?pageId=12345
      https://wiki.example.com/display/SPACE/Page+Title

    Returns a JSON object with: id, title, space, version, url, and the page body
    converted to markdown.
    """
    client = _get_client()
    try:
        result = client.read_page_content(page_url)
        return _ok(result)
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
    Use the space key (e.g. "DEV", "DOCS") when creating pages with create_page.
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


# ── Write tools ───────────────────────────────────────────────────────────────


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def create_page(
    space_key: str,
    title: str,
    content: str,
    ctx: Context,
    parent_id: str | None = None,
) -> str:
    """Create a new Confluence page with markdown content.

    Args:
        space_key: Key of the target space (e.g. "DEV", "DOCS"). Use list_spaces to find it.
        title: Page title (must be unique within the space).
        content: Page body in markdown format.
        parent_id: Optional numeric ID of the parent page. When omitted the page is created
                   at the space root. Use list_children or get_page to find parent IDs.

    Returns a JSON object with the new page's id, title, and url.
    """
    await _confirm_write(ctx, f"Create page '{title}' in space '{space_key}'")
    client = _get_client()
    with _silence_stdout():
        try:
            # TODO: wrap blocking client call in asyncio.to_thread if concurrency needed
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
async def edit_page(page_url: str, content: str, ctx: Context) -> str:
    """Replace the full body of a Confluence page with new markdown content.

    The existing page content is completely overwritten. Use add_content_to_page
    if you only want to append or prepend without discarding the current body.

    Returns a JSON object with the page's id, title, new version number, and url.
    """
    await _confirm_write(ctx, f"Overwrite full content of page at {page_url}")
    client = _get_client()
    with _silence_stdout():
        try:
            # TODO: wrap blocking client call in asyncio.to_thread if concurrency needed
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
async def add_content_to_page(
    page_url: str,
    content: str,
    ctx: Context,
    append: bool = True,
) -> str:
    """Add markdown content to an existing Confluence page without replacing it.

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
        # TODO: wrap blocking client call in asyncio.to_thread if concurrency needed
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


# ── MCP Resource ──────────────────────────────────────────────────────────────


@mcp.resource("confluence://page/{page_id}")
def page_resource(page_id: str) -> str:
    """Return a Confluence page as a markdown MCP resource.

    Access via URI: confluence://page/{page_id}
    The page body is converted from Confluence storage format to markdown.
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


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
