"""Tests for the MCP server module (confluence_markdown.mcp_server).

Strategy: patch `confluence_markdown.mcp_server._get_client` so every tool
function receives a MagicMock instead of a real ConfluenceClient.  The module-
level singletons (_client, _writes_confirmed_session) are also reset between
tests to avoid state leakage.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import confluence_markdown.mcp_server as mcp_mod
from mcp.server.elicitation import AcceptedElicitation
from confluence_markdown.mcp_server import WriteConfirmation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**overrides) -> MagicMock:
    """Return a MagicMock that mimics ConfluenceClient."""
    mock = MagicMock()
    mock.base_url = "https://confluence.example.com"
    mock._build_text_search_cql.return_value = 'text ~ "hello"'
    mock.search_pages.return_value = [{"id": "1", "title": "Page A", "url": "https://confluence.example.com/a"}]
    mock.read_page_content.return_value = {
        "id": "1",
        "title": "Page A",
        "space": "Dev",
        "space_key": "DEV",
        "version": 1,
        "url": "https://confluence.example.com/a",
        "html_content": "<p>Hello</p>",
        "markdown_content": "Hello",
    }
    mock.list_recent_pages.return_value = [{"id": "2", "title": "Recent", "url": "https://confluence.example.com/r"}]
    mock.list_spaces.return_value = [{"key": "DEV", "name": "Development"}]
    mock.list_children.return_value = [{"id": "3", "title": "Child", "url": "https://confluence.example.com/c"}]
    mock.create_page.return_value = {"id": "42", "title": "New Page", "_links": {"webui": "/pages/42"}}
    mock.edit_page_with_editor.return_value = {"id": "1", "title": "Page A", "version": {"number": 2}}
    mock.add_content_to_page.return_value = {"id": "1", "title": "Page A", "version": {"number": 3}}
    mock.get_page_content.return_value = {
        "title": "Page A",
        "body": {"storage": {"value": "<p>Hello</p>"}},
    }
    mock._html_to_markdown.return_value = "Hello"
    mock._prettify_storage.return_value = "<p>Hello</p>"
    mock._validate_storage_xhtml.return_value = (True, None)
    for key, value in overrides.items():
        setattr(mock, key, value)
    return mock


def _patch_client(mock: MagicMock):
    """Context manager: patch _get_client and reset the module singleton."""
    return patch.object(mcp_mod, "_get_client", return_value=mock)


def _make_ctx(confirm: bool = True, remember: bool = False, supports_elicitation: bool = True) -> MagicMock:
    """Return a mock Context whose elicit() returns an AcceptedElicitation."""
    ctx = MagicMock()
    ctx.session.check_client_capability.return_value = supports_elicitation
    ctx.elicit = AsyncMock(
        return_value=AcceptedElicitation(data=WriteConfirmation(confirm=confirm, remember=remember))
    )
    return ctx


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset module-level singletons before each test."""
    mcp_mod._client = None
    mcp_mod._writes_confirmed_session = False
    yield
    mcp_mod._client = None
    mcp_mod._writes_confirmed_session = False


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """Verify that all expected tools are registered on the FastMCP instance."""

    def _tool_names(self) -> set[str]:
        tools = asyncio.run(mcp_mod.mcp.list_tools())
        return {t.name for t in tools}

    def test_navigation_tools_registered(self):
        names = self._tool_names()
        for tool in ("search_pages", "list_recent_pages", "list_spaces", "list_children"):
            assert tool in names, f"Expected navigation tool '{tool}' to be registered"

    def test_md_tools_registered(self):
        names = self._tool_names()
        for tool in ("get_page_md", "create_page_md", "edit_page_md", "add_content_md"):
            assert tool in names, f"Expected *_md tool '{tool}' to be registered"

    def test_storage_tools_registered(self):
        names = self._tool_names()
        for tool in ("get_page_storage", "create_page_storage", "edit_page_storage", "add_content_storage"):
            assert tool in names, f"Expected *_storage tool '{tool}' to be registered"

    def test_old_tool_names_not_present(self):
        """Ensure the pre-rename tool names are gone (breaking-change clean cut)."""
        names = self._tool_names()
        for old in ("get_page", "create_page", "edit_page", "add_content_to_page"):
            assert old not in names, f"Old tool name '{old}' should have been removed"


# ---------------------------------------------------------------------------
# Navigation / search tools
# ---------------------------------------------------------------------------


class TestSearchPages:
    def test_cql_search(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.search_pages(cql="space = DEV")
        mock.search_pages.assert_called_once_with("space = DEV", 10)
        data = json.loads(result)
        assert data[0]["title"] == "Page A"

    def test_text_query_builds_cql(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.search_pages(query="hello")
        mock._build_text_search_cql.assert_called_once_with("hello")
        mock.search_pages.assert_called_once_with('text ~ "hello"', 10)
        assert "Page A" in result

    def test_no_query_raises(self):
        mock = _make_client()
        with _patch_client(mock):
            with pytest.raises(ValueError, match="cql.*query"):
                mcp_mod.search_pages()

    def test_limit_clamped_to_50(self):
        mock = _make_client()
        with _patch_client(mock):
            mcp_mod.search_pages(cql="type = page", limit=999)
        _, called_limit = mock.search_pages.call_args[0]
        assert called_limit == 50

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.search_pages.side_effect = ConfluenceError("boom")
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="boom"):
                mcp_mod.search_pages(cql="type = page")


class TestListRecentPages:
    def test_returns_json_list(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.list_recent_pages(limit=5)
        mock.list_recent_pages.assert_called_once_with(5)
        data = json.loads(result)
        assert data[0]["title"] == "Recent"

    def test_limit_clamped(self):
        mock = _make_client()
        with _patch_client(mock):
            mcp_mod.list_recent_pages(limit=100)
        mock.list_recent_pages.assert_called_once_with(50)


class TestListSpaces:
    def test_returns_json_list(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.list_spaces()
        mock.list_spaces.assert_called_once()
        data = json.loads(result)
        assert data[0]["key"] == "DEV"


class TestListChildren:
    def test_returns_json_list(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.list_children("https://confluence.example.com/parent")
        mock.list_children.assert_called_once_with("https://confluence.example.com/parent", 50)
        data = json.loads(result)
        assert data[0]["title"] == "Child"

    def test_limit_clamped_to_200(self):
        mock = _make_client()
        with _patch_client(mock):
            mcp_mod.list_children("https://confluence.example.com/parent", limit=999)
        _, called_limit = mock.list_children.call_args[0]
        assert called_limit == 200


# ---------------------------------------------------------------------------
# *_md tools
# ---------------------------------------------------------------------------


class TestGetPageMd:
    def test_returns_json(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.get_page_md("https://confluence.example.com/a")
        mock.read_page_content.assert_called_once_with("https://confluence.example.com/a")
        data = json.loads(result)
        assert data["title"] == "Page A"

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.read_page_content.side_effect = ConfluenceError("not found")
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="not found"):
                mcp_mod.get_page_md("https://confluence.example.com/missing")


class TestCreatePageMd:
    def test_creates_page_and_returns_url(self):
        mock = _make_client()
        ctx = _make_ctx()
        with _patch_client(mock):
            result = asyncio.run(mcp_mod.create_page_md(
                space_key="DEV",
                title="New Page",
                content="# Hello",
                ctx=ctx,
                parent_id=None,
            ))
        mock.create_page.assert_called_once_with(
            space_key="DEV",
            title="New Page",
            content="# Hello",
            parent_id=None,
            content_type="markdown",
        )
        data = json.loads(result)
        assert data["id"] == "42"
        assert "42" in data["url"]

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.create_page.side_effect = ConfluenceError("space not found")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="space not found"):
                asyncio.run(mcp_mod.create_page_md("MISSING", "Title", "body", ctx=ctx))


class TestEditPageMd:
    def test_edits_page_and_returns_metadata(self):
        mock = _make_client()
        ctx = _make_ctx()
        with _patch_client(mock):
            result = asyncio.run(
                mcp_mod.edit_page_md("https://confluence.example.com/a", "# Updated", ctx=ctx)
            )
        mock.edit_page_with_editor.assert_called_once_with(
            "https://confluence.example.com/a",
            content="# Updated",
            content_type="markdown",
        )
        data = json.loads(result)
        assert data["version"] == 2

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.edit_page_with_editor.side_effect = ConfluenceError("conflict")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="conflict"):
                asyncio.run(mcp_mod.edit_page_md("https://confluence.example.com/a", "body", ctx=ctx))


class TestAddContentMd:
    def test_appends_content(self):
        mock = _make_client()
        ctx = _make_ctx()
        with _patch_client(mock):
            result = asyncio.run(mcp_mod.add_content_md(
                "https://confluence.example.com/a", "## New section", ctx=ctx, append=True
            ))
        mock.add_content_to_page.assert_called_once_with(
            "https://confluence.example.com/a",
            "## New section",
            append=True,
            content_type="markdown",
        )
        data = json.loads(result)
        assert data["version"] == 3

    def test_prepends_content(self):
        mock = _make_client()
        ctx = _make_ctx()
        with _patch_client(mock):
            asyncio.run(mcp_mod.add_content_md(
                "https://confluence.example.com/a", "## Intro", ctx=ctx, append=False
            ))
        mock.add_content_to_page.assert_called_once_with(
            "https://confluence.example.com/a",
            "## Intro",
            append=False,
            content_type="markdown",
        )

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.add_content_to_page.side_effect = ConfluenceError("page locked")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="page locked"):
                asyncio.run(mcp_mod.add_content_md(
                    "https://confluence.example.com/a", "body", ctx=ctx
                ))


# ---------------------------------------------------------------------------
# *_storage tools
# ---------------------------------------------------------------------------


class TestGetPageStorage:
    def test_returns_storage_content(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.get_page_storage("https://confluence.example.com/a")
        mock.read_page_content.assert_called_once_with("https://confluence.example.com/a")
        mock._prettify_storage.assert_called_once_with("<p>Hello</p>")
        data = json.loads(result)
        assert data["title"] == "Page A"
        assert "storage_content" in data
        assert "markdown_content" not in data  # storage tool does not return markdown

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.read_page_content.side_effect = ConfluenceError("not found")
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="not found"):
                mcp_mod.get_page_storage("https://confluence.example.com/missing")


class TestCreatePageStorage:
    def test_creates_page_with_storage_content(self):
        mock = _make_client()
        ctx = _make_ctx()
        xhtml = "<p>Hello <strong>world</strong></p>"
        with _patch_client(mock):
            result = asyncio.run(mcp_mod.create_page_storage(
                space_key="DEV",
                title="New Page",
                content=xhtml,
                ctx=ctx,
            ))
        mock._validate_storage_xhtml.assert_called_once_with(xhtml)
        mock.create_page.assert_called_once_with(
            space_key="DEV",
            title="New Page",
            content=xhtml,
            parent_id=None,
            content_type="html",
        )
        data = json.loads(result)
        assert data["id"] == "42"
        assert "42" in data["url"]

    def test_invalid_xhtml_raises_value_error(self):
        mock = _make_client()
        mock._validate_storage_xhtml.return_value = (False, "unclosed tag <p>")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(ValueError, match="unclosed tag"):
                asyncio.run(mcp_mod.create_page_storage(
                    "DEV", "Title", "<p>broken", ctx=ctx
                ))

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.create_page.side_effect = ConfluenceError("space not found")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="space not found"):
                asyncio.run(mcp_mod.create_page_storage("MISSING", "Title", "<p/>", ctx=ctx))


class TestEditPageStorage:
    def test_edits_page_with_storage_content(self):
        mock = _make_client()
        ctx = _make_ctx()
        xhtml = "<p>Updated <strong>content</strong></p>"
        with _patch_client(mock):
            result = asyncio.run(
                mcp_mod.edit_page_storage("https://confluence.example.com/a", xhtml, ctx=ctx)
            )
        mock._validate_storage_xhtml.assert_called_once_with(xhtml)
        mock.edit_page_with_editor.assert_called_once_with(
            "https://confluence.example.com/a",
            content=xhtml,
            content_type="storage",
        )
        data = json.loads(result)
        assert data["version"] == 2

    def test_invalid_xhtml_raises_value_error(self):
        mock = _make_client()
        mock._validate_storage_xhtml.return_value = (False, "bare & detected")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(ValueError, match="bare &"):
                asyncio.run(
                    mcp_mod.edit_page_storage("https://confluence.example.com/a", "bad & content", ctx=ctx)
                )

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.edit_page_with_editor.side_effect = ConfluenceError("conflict")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="conflict"):
                asyncio.run(
                    mcp_mod.edit_page_storage("https://confluence.example.com/a", "<p/>", ctx=ctx)
                )


class TestAddContentStorage:
    def test_appends_storage_content(self):
        mock = _make_client()
        ctx = _make_ctx()
        xhtml = "<p>Appended</p>"
        with _patch_client(mock):
            result = asyncio.run(mcp_mod.add_content_storage(
                "https://confluence.example.com/a", xhtml, ctx=ctx, append=True
            ))
        mock._validate_storage_xhtml.assert_called_once_with(xhtml)
        mock.add_content_to_page.assert_called_once_with(
            "https://confluence.example.com/a",
            xhtml,
            append=True,
            content_type="html",
        )
        data = json.loads(result)
        assert data["version"] == 3

    def test_invalid_xhtml_raises_value_error(self):
        mock = _make_client()
        mock._validate_storage_xhtml.return_value = (False, "unclosed tag")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(ValueError, match="unclosed tag"):
                asyncio.run(mcp_mod.add_content_storage(
                    "https://confluence.example.com/a", "<p>broken", ctx=ctx
                ))

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.add_content_to_page.side_effect = ConfluenceError("page locked")
        ctx = _make_ctx()
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="page locked"):
                asyncio.run(mcp_mod.add_content_storage(
                    "https://confluence.example.com/a", "<p/>", ctx=ctx
                ))


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------


class TestPageResource:
    def test_returns_markdown_with_title(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.page_resource("12345")
        mock.get_page_content.assert_called_once_with("12345")
        assert result.startswith("# Page A")
        assert "Hello" in result

    def test_error_raises_runtime(self):
        mock = _make_client()
        mock.get_page_content.side_effect = Exception("network error")
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="network error"):
                mcp_mod.page_resource("99999")


class TestPageResourceStorage:
    def test_returns_storage_xhtml(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.page_resource_storage("12345")
        mock.get_page_content.assert_called_once_with("12345")
        mock._prettify_storage.assert_called_once_with("<p>Hello</p>")
        assert "Page A" in result

    def test_error_raises_runtime(self):
        mock = _make_client()
        mock.get_page_content.side_effect = Exception("network error")
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="network error"):
                mcp_mod.page_resource_storage("99999")


# ---------------------------------------------------------------------------
# Human-in-the-loop confirmation (_confirm_write)
# ---------------------------------------------------------------------------


class TestConfirmWrite:
    def test_no_elicitation_support_proceeds(self):
        mock = _make_client()
        ctx = _make_ctx(supports_elicitation=False)
        with _patch_client(mock):
            # Should NOT raise even though we never elicit
            asyncio.run(mcp_mod.edit_page_md("https://confluence.example.com/a", "body", ctx=ctx))
        ctx.elicit.assert_not_called()

    def test_user_declines_raises_permission_error(self):
        from mcp.server.elicitation import DeclinedElicitation
        mock = _make_client()
        ctx = _make_ctx()
        ctx.elicit = AsyncMock(return_value=DeclinedElicitation())
        with _patch_client(mock):
            with pytest.raises(PermissionError):
                asyncio.run(mcp_mod.edit_page_md("https://confluence.example.com/a", "body", ctx=ctx))

    def test_remember_skips_subsequent_prompts(self):
        mock = _make_client()
        ctx = _make_ctx(remember=True)
        with _patch_client(mock):
            asyncio.run(mcp_mod.edit_page_md("https://confluence.example.com/a", "body", ctx=ctx))
            # Second call: _writes_confirmed_session is True, elicit should not be called again
            asyncio.run(mcp_mod.edit_page_md("https://confluence.example.com/b", "body", ctx=ctx))
        assert ctx.elicit.call_count == 1


# ---------------------------------------------------------------------------
# Credential resolution (_get_client)
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_env_vars_used_when_set(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_URL", "https://env.example.com")
        monkeypatch.setenv("CONFLUENCE_TOKEN", "tok123")
        monkeypatch.delenv("CONFLUENCE_USERNAME", raising=False)
        monkeypatch.delenv("CONFLUENCE_PASSWORD", raising=False)

        with patch("confluence_markdown.mcp_server.ConfigManager") as MockCM, \
             patch("confluence_markdown.mcp_server.ConfluenceClient") as MockCC:
            MockCM.return_value.load_config.return_value = {}
            MockCC.return_value = MagicMock()
            mcp_mod._get_client()

        MockCC.assert_called_once()
        call_kwargs = MockCC.call_args[1]
        assert call_kwargs["base_url"] == "https://env.example.com"
        assert call_kwargs["token"] == "tok123"

    def test_missing_base_url_raises_configuration_error(self, monkeypatch):
        from confluence_markdown.exceptions import ConfigurationError
        monkeypatch.delenv("CONFLUENCE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_USERNAME", raising=False)
        monkeypatch.delenv("CONFLUENCE_PASSWORD", raising=False)

        with patch("confluence_markdown.mcp_server.ConfigManager") as MockCM:
            MockCM.return_value.load_config.return_value = {}
            with pytest.raises(ConfigurationError, match="base_url"):
                mcp_mod._get_client()

    def test_missing_credentials_raises_configuration_error(self, monkeypatch):
        from confluence_markdown.exceptions import ConfigurationError
        monkeypatch.setenv("CONFLUENCE_URL", "https://env.example.com")
        monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_USERNAME", raising=False)
        monkeypatch.delenv("CONFLUENCE_PASSWORD", raising=False)

        with patch("confluence_markdown.mcp_server.ConfigManager") as MockCM:
            MockCM.return_value.load_config.return_value = {}
            with pytest.raises(ConfigurationError, match="credentials"):
                mcp_mod._get_client()

    def test_singleton_cached(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_URL", "https://env.example.com")
        monkeypatch.setenv("CONFLUENCE_TOKEN", "tok123")

        with patch("confluence_markdown.mcp_server.ConfigManager") as MockCM, \
             patch("confluence_markdown.mcp_server.ConfluenceClient") as MockCC:
            MockCM.return_value.load_config.return_value = {}
            MockCC.return_value = MagicMock()
            c1 = mcp_mod._get_client()
            c2 = mcp_mod._get_client()

        assert c1 is c2
        MockCC.assert_called_once()
