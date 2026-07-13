"""Tests for the async batch methods of ConfluenceClient.

Strategy: the low-level `_async_request` takes the httpx client as an
argument, so it is tested with a plain mock.  The higher-level methods
create their own `httpx.AsyncClient`, so `httpx.AsyncClient` is patched
inside the client module to return a mock async context manager.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import confluence_markdown.client as client_mod
from confluence_markdown.main import ConfluenceClient


def make_client() -> ConfluenceClient:
    return ConfluenceClient(base_url="https://example.com", token="test-token")


def make_response(status: int = 200, json_data=None, headers=None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = ""
    return resp


def make_async_client(side_effect):
    """Return (context_manager, inner_client) mocking httpx.AsyncClient."""
    inner = MagicMock()
    inner.request = AsyncMock(side_effect=side_effect)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, inner


class TestAsyncRequest:
    """Tests for _async_request retry behaviour."""

    def test_success_returns_response(self):
        client = make_client()
        response = make_response(200, {"ok": True})
        inner = MagicMock()
        inner.request = AsyncMock(return_value=response)

        result = asyncio.run(
            client._async_request(inner, "GET", "https://example.com/x")
        )
        assert result is response
        inner.request.assert_awaited_once_with("GET", "https://example.com/x")

    def test_retries_on_429_with_retry_after(self):
        client = make_client()
        rate_limited = make_response(429, headers={"Retry-After": "2"})
        ok = make_response(200)
        inner = MagicMock()
        inner.request = AsyncMock(side_effect=[rate_limited, ok])

        with patch.object(
            client_mod.asyncio, "sleep", new=AsyncMock()
        ) as mock_sleep:
            result = asyncio.run(
                client._async_request(inner, "GET", "https://example.com/x")
            )

        assert result is ok
        mock_sleep.assert_awaited_once_with(2)
        assert inner.request.await_count == 2

    def test_retries_on_429_with_invalid_retry_after(self):
        client = make_client()
        rate_limited = make_response(429, headers={"Retry-After": "soon"})
        ok = make_response(200)
        inner = MagicMock()
        inner.request = AsyncMock(side_effect=[rate_limited, ok])

        with patch.object(
            client_mod.asyncio, "sleep", new=AsyncMock()
        ) as mock_sleep:
            result = asyncio.run(
                client._async_request(inner, "GET", "https://example.com/x")
            )

        assert result is ok
        mock_sleep.assert_awaited_once_with(60)

    def test_retries_on_server_error_then_succeeds(self):
        client = make_client()
        error = make_response(500)
        ok = make_response(200)
        inner = MagicMock()
        inner.request = AsyncMock(side_effect=[error, ok])

        with patch.object(client_mod.asyncio, "sleep", new=AsyncMock()):
            result = asyncio.run(
                client._async_request(inner, "GET", "https://example.com/x")
            )
        assert result is ok

    def test_raises_last_connection_error_after_retries(self):
        client = make_client()
        inner = MagicMock()
        inner.request = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with patch.object(client_mod.asyncio, "sleep", new=AsyncMock()):
            with pytest.raises(httpx.ConnectError):
                asyncio.run(
                    client._async_request(inner, "GET", "https://example.com/x")
                )
        assert inner.request.await_count == 3


class TestAsyncPageMethods:
    """Tests for the async page-level methods."""

    def test_get_page_content_success(self):
        client = make_client()
        page = {"id": "123", "title": "Test"}
        cm, inner = make_async_client([make_response(200, page)])

        with patch.object(client_mod.httpx, "AsyncClient", return_value=cm):
            result = asyncio.run(client.async_get_page_content("123"))

        assert result == page
        args, kwargs = inner.request.await_args
        assert args == ("GET", f"{client.api_base}/content/123")
        assert kwargs["params"]["expand"] == "body.storage,space,version,ancestors"

    def test_get_page_content_error_raises(self):
        client = make_client()
        cm, _ = make_async_client([make_response(404)])

        with patch.object(client_mod.httpx, "AsyncClient", return_value=cm):
            with pytest.raises(RuntimeError, match="HTTP 404"):
                asyncio.run(client.async_get_page_content("123"))

    def test_list_children_maps_fields(self):
        client = make_client()
        payload = {
            "results": [
                {
                    "id": "42",
                    "title": "Child",
                    "space": {"key": "DOCS"},
                    "version": {"when": "2026-01-01"},
                },
                {"title": "no id — skipped"},
            ]
        }
        cm, _ = make_async_client([make_response(200, payload)])

        with patch.object(client_mod.httpx, "AsyncClient", return_value=cm):
            children = asyncio.run(client.async_list_children("1"))

        assert children == [
            {
                "id": "42",
                "title": "Child",
                "space": "DOCS",
                "last_modified": "2026-01-01",
                "url": f"{client.base_url}/pages/viewpage.action?pageId=42",
            }
        ]

    def test_get_pages_batch_skips_failures(self):
        client = make_client()
        ok = make_response(200, {"id": "1"})
        not_found = make_response(404)
        cm, _ = make_async_client([ok, not_found])

        with patch.object(client_mod.httpx, "AsyncClient", return_value=cm):
            results = asyncio.run(client.async_get_pages_batch(["1", "2"]))

        assert results == [{"id": "1"}]

    def test_list_children_recursive_sets_depth(self):
        client = make_client()
        root_children = {
            "results": [
                {
                    "id": "10",
                    "title": "Level 0",
                    "space": {"key": "DOCS"},
                    "version": {"when": "x"},
                }
            ]
        }
        grandchildren = {
            "results": [
                {
                    "id": "20",
                    "title": "Level 1",
                    "space": {"key": "DOCS"},
                    "version": {"when": "x"},
                }
            ]
        }
        empty = {"results": []}
        cm, _ = make_async_client(
            [
                make_response(200, root_children),
                make_response(200, grandchildren),
                make_response(200, empty),
            ]
        )

        with patch.object(client_mod.httpx, "AsyncClient", return_value=cm):
            result = asyncio.run(client.async_list_children_recursive("1"))

        assert [(p["id"], p["depth"]) for p in result] == [("10", 0), ("20", 1)]

    def test_list_children_recursive_respects_max_depth(self):
        client = make_client()
        result = asyncio.run(
            client.async_list_children_recursive("1", max_depth=0)
        )
        assert result == []

    def test_download_pages_batch_builds_markdown(self):
        client = make_client()
        page = {
            "id": "123",
            "title": "My Page",
            "body": {"storage": {"value": "<p>Hello <b>world</b></p>"}},
            "space": {"name": "Docs"},
            "version": {"number": 7},
        }

        with patch.object(
            client, "async_get_pages_batch", new=AsyncMock(return_value=[page])
        ) as mock_batch:
            results = asyncio.run(
                client.async_download_pages_batch(
                    ["https://example.com/pages/viewpage.action?pageId=123"]
                )
            )

        mock_batch.assert_awaited_once_with(["123"])
        assert len(results) == 1
        title, markdown = results[0]
        assert title == "My Page"
        assert "# My Page" in markdown
        assert "**Page ID:** 123" in markdown
        assert "**Version:** 7" in markdown
        assert "Hello **world**" in markdown


class TestSyncWrappers:
    """The sync wrappers must drive the async methods via asyncio.run."""

    def test_download_pages_parallel(self):
        client = make_client()
        with patch.object(
            client,
            "async_download_pages_batch",
            new=AsyncMock(return_value=[("T", "md")]),
        ):
            assert client.download_pages_parallel(["url"]) == [("T", "md")]

    def test_list_children_recursive_parallel(self):
        client = make_client()
        with patch.object(
            client, "get_page_by_url", return_value={"id": "99"}
        ), patch.object(
            client,
            "async_list_children_recursive",
            new=AsyncMock(return_value=[{"id": "1", "depth": 0}]),
        ) as mock_rec:
            result = client.list_children_recursive_parallel("url", max_depth=3)

        assert result == [{"id": "1", "depth": 0}]
        mock_rec.assert_awaited_once_with("99", 3)
