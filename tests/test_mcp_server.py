"""Tests for the MCP server module (confluence_markdown.mcp_server).

Strategy: patch `confluence_markdown.mcp_server._get_client` so every tool
function receives a MagicMock instead of a real ConfluenceClient.  The module-
level singleton `_client` is also reset between tests to avoid state leakage.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

import confluence_markdown.mcp_server as mcp_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**overrides) -> MagicMock:
    """Return a MagicMock that mimics ConfluenceClient."""
    mock = MagicMock()
    mock.base_url = "https://confluence.example.com"
    mock._build_text_search_cql.return_value = 'text ~ "hello"'
    mock.search_pages.return_value = [{"id": "1", "title": "Page A", "url": "https://confluence.example.com/a"}]
    mock.read_page_content.return_value = {"id": "1", "title": "Page A", "markdown": "# Hello"}
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
    for key, value in overrides.items():
        setattr(mock, key, value)
    return mock


def _patch_client(mock: MagicMock):
    """Context manager: patch _get_client and reset the module singleton."""
    return patch.object(mcp_mod, "_get_client", return_value=mock)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the module-level _client singleton before each test."""
    mcp_mod._client = None
    yield
    mcp_mod._client = None


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """Verify that all expected tools are registered on the FastMCP instance."""

    def _tool_names(self) -> set[str]:
        import asyncio
        tools = asyncio.run(mcp_mod.mcp.list_tools())
        return {t.name for t in tools}

    def test_read_tools_registered(self):
        names = self._tool_names()
        for tool in ("search_pages", "get_page", "list_recent_pages", "list_spaces", "list_children"):
            assert tool in names, f"Expected read tool '{tool}' to be registered"

    def test_write_tools_registered(self):
        """Write tools are always registered (gating is runtime, not registration-time)."""
        names = self._tool_names()
        for tool in ("create_page", "edit_page", "add_content_to_page"):
            assert tool in names, f"Expected write tool '{tool}' to be registered"


# ---------------------------------------------------------------------------
# Read tools
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


class TestGetPage:
    def test_returns_json(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.get_page("https://confluence.example.com/a")
        mock.read_page_content.assert_called_once_with("https://confluence.example.com/a")
        data = json.loads(result)
        assert data["title"] == "Page A"

    def test_confluence_error_raises_runtime(self):
        from confluence_markdown.exceptions import ConfluenceError
        mock = _make_client()
        mock.read_page_content.side_effect = ConfluenceError("not found")
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="not found"):
                mcp_mod.get_page("https://confluence.example.com/missing")


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
# Write tools
# ---------------------------------------------------------------------------


class TestCreatePage:
    def test_creates_page_and_returns_url(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.create_page(
                space_key="DEV",
                title="New Page",
                content="# Hello",
                parent_id=None,
            )
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
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="space not found"):
                mcp_mod.create_page("MISSING", "Title", "body")


class TestEditPage:
    def test_edits_page_and_returns_metadata(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.edit_page("https://confluence.example.com/a", "# Updated")
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
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="conflict"):
                mcp_mod.edit_page("https://confluence.example.com/a", "body")


class TestAddContentToPage:
    def test_appends_content(self):
        mock = _make_client()
        with _patch_client(mock):
            result = mcp_mod.add_content_to_page(
                "https://confluence.example.com/a", "## New section", append=True
            )
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
        with _patch_client(mock):
            mcp_mod.add_content_to_page(
                "https://confluence.example.com/a", "## Intro", append=False
            )
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
        with _patch_client(mock):
            with pytest.raises(RuntimeError, match="page locked"):
                mcp_mod.add_content_to_page("https://confluence.example.com/a", "body")


# ---------------------------------------------------------------------------
# MCP Resource
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
