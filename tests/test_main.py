"""Tests for the main confluence-markdown functionality."""

from pathlib import Path

import pytest

from confluence_markdown.main import ConfigManager, ConfluenceClient


def test_config_manager_init():
    """Test ConfigManager initialization."""
    config = ConfigManager()
    assert config.config_dir == Path.home() / ".config" / "confluence-markdown"
    assert config.config_file == config.config_dir / "config.json"


def test_url_parsing():
    """Test URL parsing functionality."""
    client = ConfluenceClient(
        base_url="https://example.confluence.com", token="test-token"
    )

    # Test different URL formats
    test_cases = [
        ("https://example.com/pages/viewpage.action?pageId=123456", "123456"),
        ("https://example.com/spaces/SPACE/pages/123456/Page+Title", "123456"),
    ]

    for url, expected_id in test_cases:
        result = client._extract_page_id_from_url(url)
        assert result == expected_id, f"Failed to parse {url}"


def test_recent_pages_cql_variants():
    """Ensure the recent pages CQL variants are stable."""
    client = ConfluenceClient(
        base_url="https://example.confluence.com",
        token="test-token",
    )
    assert client._recent_pages_cql_variants() == [
        "type=page AND lastModifiedBy=currentUser() order by lastmodified desc",
        "type=page AND contributor=currentUser() order by lastmodified desc",
        "type=page AND creator=currentUser() order by lastmodified desc",
        "type=page order by lastmodified desc",
    ]


def test_url_parsing_rejects_non_immediate_segment():
    """Only accept the segment immediately after /pages/."""
    client = ConfluenceClient(
        base_url="https://example.confluence.com",
        token="test-token",
    )
    url = "https://example.com/spaces/SPACE/pages/notanid/123456"
    assert client._extract_page_id_from_url(url) is None


def test_escape_markdown_heading():
    """Escape characters that would break heading rendering."""
    client = ConfluenceClient(
        base_url="https://example.confluence.com",
        token="test-token",
    )
    title = "Title #1 \\ test\nnext"
    assert client._escape_markdown_heading(title) == "Title \\#1 \\\\ test next"


def test_client_initialization_with_token():
    """Test client initialization with token."""
    client = ConfluenceClient(base_url="https://example.com", token="test-token")
    assert client.base_url == "https://example.com"
    assert "Authorization" in client.session.headers


def test_client_initialization_with_username_password():
    """Test client initialization with username/password."""
    client = ConfluenceClient(
        base_url="https://example.com", username="test-user", password="test-pass"
    )
    assert client.base_url == "https://example.com"
    assert "Authorization" in client.session.headers


def test_client_initialization_with_username_and_token():
    """Test client initialization with username and token (PAT mode)."""
    client = ConfluenceClient(
        base_url="https://example.com", username="test-user", token="test-token"
    )
    assert client.base_url == "https://example.com"
    assert "Authorization" in client.session.headers


def test_client_initialization_fails_without_auth():
    """Test client initialization fails without authentication."""
    with pytest.raises(
        ValueError, match="Either token or username/password must be provided"
    ):
        ConfluenceClient(base_url="https://example.com")
