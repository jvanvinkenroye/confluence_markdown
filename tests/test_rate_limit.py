"""Tests for 429 rate-limit handling in the synchronous request path."""

import time
from unittest.mock import MagicMock

import pytest
import requests

from confluence_markdown.main import ConfluenceClient


def make_client() -> ConfluenceClient:
    return ConfluenceClient(base_url="https://example.com", token="test-token")


def make_response(status: int = 200, headers=None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = headers or {}
    return resp


class TestHandleRateLimit:
    """Tests for _handle_rate_limit."""

    def test_sleeps_on_429_with_retry_after(self, monkeypatch):
        client = make_client()
        sleeps = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client._handle_rate_limit(make_response(429, {"Retry-After": "7"}))
        assert sleeps == [7]

    def test_default_wait_on_invalid_retry_after(self, monkeypatch):
        client = make_client()
        sleeps = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client._handle_rate_limit(make_response(429, {"Retry-After": "later"}))
        assert sleeps == [60]

    def test_default_wait_without_retry_after(self, monkeypatch):
        client = make_client()
        sleeps = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client._handle_rate_limit(make_response(429))
        assert sleeps == [60]

    def test_no_sleep_on_success(self, monkeypatch):
        client = make_client()
        sleeps = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client._handle_rate_limit(make_response(200))
        assert sleeps == []

    def test_warns_when_remaining_low(self, monkeypatch, caplog):
        client = make_client()
        monkeypatch.setattr(time, "sleep", lambda _: None)

        with caplog.at_level("WARNING"):
            client._handle_rate_limit(
                make_response(200, {"X-RateLimit-Remaining": "3"})
            )
        assert "Rate limit nearly exhausted" in caplog.text

    def test_no_warning_when_remaining_high(self, caplog):
        client = make_client()
        with caplog.at_level("WARNING"):
            client._handle_rate_limit(
                make_response(200, {"X-RateLimit-Remaining": "100"})
            )
        assert "Rate limit nearly exhausted" not in caplog.text

    def test_invalid_remaining_header_ignored(self, caplog):
        client = make_client()
        with caplog.at_level("WARNING"):
            client._handle_rate_limit(
                make_response(200, {"X-RateLimit-Remaining": "many"})
            )
        assert caplog.text == ""


class TestRequestRateLimitRetry:
    """_request must retry once after a 429 (post-sleep)."""

    def test_retries_after_429(self, monkeypatch):
        client = make_client()
        monkeypatch.setattr(time, "sleep", lambda _: None)

        rate_limited = make_response(429, {"Retry-After": "1"})
        ok = make_response(200)
        client.session.request = MagicMock(side_effect=[rate_limited, ok])

        result = client._request("GET", "https://example.com/x")
        assert result is ok
        assert client.session.request.call_count == 2

    def test_no_retry_on_success(self, monkeypatch):
        client = make_client()
        monkeypatch.setattr(time, "sleep", lambda _: None)

        ok = make_response(200)
        client.session.request = MagicMock(return_value=ok)

        result = client._request("GET", "https://example.com/x")
        assert result is ok
        client.session.request.assert_called_once()

    def test_server_error_raises(self, monkeypatch):
        client = make_client()
        monkeypatch.setattr(time, "sleep", lambda _: None)

        error = make_response(500)
        error.raise_for_status.side_effect = requests.HTTPError("500")
        client.session.request = MagicMock(return_value=error)

        with pytest.raises(requests.HTTPError):
            client._request("GET", "https://example.com/x")
