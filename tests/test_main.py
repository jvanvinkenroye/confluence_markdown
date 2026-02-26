"""Tests for the main confluence-markdown functionality."""

import subprocess
import sys
from pathlib import Path
import tempfile

import pytest

from confluence_markdown import __version__
from confluence_markdown.main import ConfluenceClient
from confluence_markdown.config import ConfigManager
from confluence_markdown.cache import Cache
from confluence_markdown.exceptions import (
    ConfluenceError,
    AuthenticationError,
    ConfigurationError,
    APIError,
)


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_config_manager_init(self):
        """Test ConfigManager initialization."""
        config = ConfigManager()
        assert config.config_dir == Path.home() / ".config" / "confluence-markdown"
        assert config.config_file == config.config_dir / "config.json"

    def test_list_profiles_empty(self):
        """Test listing profiles when no config exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ConfigManager()
            config.config_dir = Path(tmpdir)
            config.config_file = Path(tmpdir) / "config.json"
            assert config.list_profiles() == []

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ConfigManager()
            config.config_dir = Path(tmpdir)
            config.config_file = Path(tmpdir) / "config.json"

            test_config = {"base_url": "https://example.com", "token": "test"}
            config.save_config(test_config, "test_profile")

            loaded = config.load_config("test_profile")
            assert loaded == test_config

    def test_space_config(self):
        """Test space-specific configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ConfigManager()
            config.config_dir = Path(tmpdir)
            config.config_file = Path(tmpdir) / "config.json"

            # Save base config
            base_config = {
                "base_url": "https://example.com",
                "editor": "vim",
                "table_format": "markdown",
            }
            config.save_config(base_config, "default")

            # Save space config
            config.save_space_config("default", "DOCS", {"editor": "code", "table_format": "yaml"})

            # Get merged config
            merged = config.get_space_config("default", "DOCS")
            assert merged["base_url"] == "https://example.com"
            assert merged["editor"] == "code"  # Space-specific
            assert merged["table_format"] == "yaml"  # Space-specific


class TestCache:
    """Tests for Cache module."""

    def test_cache_disabled(self):
        """Test cache when disabled."""
        cache = Cache(enabled=False)
        cache.set("key", "value")
        assert cache.get("key") is None

    def test_cache_set_get(self):
        """Test basic cache set and get."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir), ttl=3600)
            cache.set("test_key", {"data": "value"})
            result = cache.get("test_key")
            assert result == {"data": "value"}

    def test_cache_miss(self):
        """Test cache miss for non-existent key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            assert cache.get("nonexistent") is None

    def test_cache_clear(self):
        """Test clearing cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            count = cache.clear()
            assert count == 2
            assert cache.get("key1") is None

    def test_cache_delete(self):
        """Test deleting specific cache entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            cache.set("key", "value")
            cache.delete("key")
            assert cache.get("key") is None


class TestExceptions:
    """Tests for custom exceptions."""

    def test_confluence_error(self):
        """Test base ConfluenceError."""
        error = ConfluenceError("test error")
        assert str(error) == "test error"

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("auth failed")
        assert isinstance(error, ConfluenceError)

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("config missing")
        assert isinstance(error, ConfluenceError)

    def test_api_error_with_status(self):
        """Test APIError with status code."""
        error = APIError("api failed", status_code=404)
        assert error.status_code == 404
        assert str(error) == "api failed"


class TestConfluenceClient:
    """Tests for ConfluenceClient."""

    def test_url_parsing(self):
        """Test URL parsing functionality."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com", token="test-token"
        )

        test_cases = [
            ("https://example.com/pages/viewpage.action?pageId=123456", "123456"),
            ("https://example.com/spaces/SPACE/pages/123456/Page+Title", "123456"),
        ]

        for url, expected_id in test_cases:
            result = client._extract_page_id_from_url(url)
            assert result == expected_id, f"Failed to parse {url}"

    def test_url_parsing_rejects_non_immediate_segment(self):
        """Only accept the segment immediately after /pages/."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        url = "https://example.com/spaces/SPACE/pages/notanid/123456"
        assert client._extract_page_id_from_url(url) is None

    def test_space_key_extraction(self):
        """Test space key extraction from URL."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )

        test_cases = [
            ("https://example.com/spaces/DOCS/pages/123", "DOCS"),
            ("https://example.com/display/WIKI/Page", "WIKI"),
            ("https://example.com/spaces/~user/pages/123", "~user"),
        ]

        for url, expected_key in test_cases:
            result = client._extract_space_key_from_url(url)
            assert result == expected_key, f"Failed to extract space from {url}"

    def test_recent_pages_cql_variants(self):
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

    def test_recently_viewed_cql_variants(self):
        """Ensure the recently viewed CQL variants are stable."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        assert client._recently_viewed_cql_variants() == [
            "type=page AND lastViewed is not EMPTY order by lastViewed desc",
            "type=page AND lastviewed is not EMPTY order by lastviewed desc",
            "type=page order by lastmodified desc",
        ]

    def test_build_text_search_cql(self):
        """Build CQL with escaped quotes."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        cql = client._build_text_search_cql('foo "bar"')
        assert cql == 'type=page AND text~"foo \\"bar\\"" order by lastmodified desc'

    def test_ensure_page_cql(self):
        """Ensure page type constraint is added when missing."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        assert client._ensure_page_cql("space = TIK") == "type=page AND (space = TIK)"
        assert (
            client._ensure_page_cql("type=page AND space = TIK")
            == "type=page AND space = TIK"
        )

    def test_escape_markdown_heading(self):
        """Escape characters that would break heading rendering."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        title = "Title #1 \\ test\nnext"
        assert client._escape_markdown_heading(title) == "Title \\#1 \\\\ test next"

    def test_html_to_markdown_with_macros(self):
        """Preserve Confluence macros as placeholders in markdown."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        html = (
            '<p>Hi</p><ac:structured-macro ac:name="toc"></ac:structured-macro><p>Bye</p>'
        )
        markdown, macro_map = client._html_to_markdown_with_macros(html)
        assert "[[CONFLUENCE-MACRO-1]]" in markdown
        assert macro_map["[[CONFLUENCE-MACRO-1]]"].startswith("<ac:structured-macro")

    def test_html_to_markdown_with_ac_image(self):
        """Preserve ac:image tags as placeholders in markdown."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        html = (
            "<p>Img</p>"
            '<ac:image ac:height="250"><ri:attachment ri:filename="x.png" /></ac:image>'
        )
        markdown, macro_map = client._html_to_markdown_with_macros(html)
        assert "[[CONFLUENCE-MACRO-1]]" in markdown
        assert macro_map["[[CONFLUENCE-MACRO-1]]"].startswith("<ac:image")

    def test_complex_table_preserved(self):
        """Test that tables with merged cells are preserved as HTML."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        html = '''
        <table>
            <tr><th colspan="2">Header</th></tr>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
        </table>
        '''
        markdown, _ = client._html_to_markdown_with_macros(html)
        # Should be preserved as HTML with comment
        assert "<!-- Complex table preserved as HTML" in markdown
        assert "colspan" in markdown

    def test_simple_table_converted(self):
        """Test that simple tables are converted to markdown."""
        client = ConfluenceClient(
            base_url="https://example.confluence.com",
            token="test-token",
        )
        html = '''
        <table>
            <tr><th>Header 1</th><th>Header 2</th></tr>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
        </table>
        '''
        markdown, _ = client._html_to_markdown_with_macros(html)
        # Should be converted to markdown table
        assert "|" in markdown
        assert "<!-- Complex table" not in markdown

    def test_client_initialization_with_token(self):
        """Test client initialization with token."""
        client = ConfluenceClient(base_url="https://example.com", token="test-token")
        assert client.base_url == "https://example.com"
        assert "Authorization" in client.session.headers

    def test_client_initialization_with_username_password(self):
        """Test client initialization with username/password."""
        client = ConfluenceClient(
            base_url="https://example.com", username="test-user", password="test-pass"
        )
        assert client.base_url == "https://example.com"
        assert "Authorization" in client.session.headers

    def test_client_initialization_with_username_and_token(self):
        """Test client initialization with username and token (PAT mode)."""
        client = ConfluenceClient(
            base_url="https://example.com", username="test-user", token="test-token"
        )
        assert client.base_url == "https://example.com"
        assert "Authorization" in client.session.headers

    def test_client_initialization_fails_without_auth(self):
        """Test client initialization fails without authentication."""
        with pytest.raises(
            ValueError, match="Either token or username/password must be provided"
        ):
            ConfluenceClient(base_url="https://example.com")

    def test_client_cache_enabled_by_default(self):
        """Test that cache is enabled by default."""
        client = ConfluenceClient(base_url="https://example.com", token="test")
        assert client.cache.enabled is True

    def test_client_cache_can_be_disabled(self):
        """Test that cache can be disabled."""
        client = ConfluenceClient(
            base_url="https://example.com", token="test", cache_enabled=False
        )
        assert client.cache.enabled is False


class TestCLI:
    """End-to-end CLI tests via subprocess."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "confluence_markdown.main", *args],
            capture_output=True,
            text=True,
        )

    def test_help_exits_zero(self):
        result = self._run("--help")
        assert result.returncode == 0
        assert "Confluence Data Center Markdown Tool" in result.stdout

    def test_version_output(self):
        result = self._run("--version")
        assert result.returncode == 0
        assert __version__ in result.stdout

    def test_missing_auth_exits_nonzero(self):
        result = self._run("--base-url", "https://example.com", "--action", "test-auth")
        assert result.returncode != 0

    def test_clear_cache_exits_zero(self):
        result = self._run("--clear-cache")
        assert result.returncode == 0
        assert "Cleared" in result.stdout
