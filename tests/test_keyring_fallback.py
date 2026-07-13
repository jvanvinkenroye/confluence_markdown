"""Tests for the keyring integration and its plaintext fallback path.

The real system keychain must never be touched, so `keyring` is always
mocked at module level inside `confluence_markdown.config`.
"""

import json
from unittest.mock import MagicMock

import keyring.errors
import pytest

import confluence_markdown.config as config_mod
from confluence_markdown.config import ConfigManager


@pytest.fixture
def manager(tmp_path) -> ConfigManager:
    mgr = ConfigManager()
    mgr.config_dir = tmp_path
    mgr.config_file = tmp_path / "config.json"
    return mgr


@pytest.fixture
def mock_keyring(monkeypatch) -> MagicMock:
    """Replace the keyring module inside config.py with an in-memory store."""
    store = {}
    mock = MagicMock()
    mock.set_password.side_effect = lambda svc, key, val: store.__setitem__(
        (svc, key), val
    )
    mock.get_password.side_effect = lambda svc, key: store.get((svc, key))
    mock.delete_password.side_effect = lambda svc, key: store.pop((svc, key), None)
    mock.errors = keyring.errors
    mock._store = store
    monkeypatch.setattr(config_mod, "keyring", mock)
    monkeypatch.setattr(config_mod, "_KEYRING_AVAILABLE", True)
    return mock


def read_raw_config(manager: ConfigManager) -> dict:
    return json.loads(manager.config_file.read_text())


class TestKeyringStorage:
    """Secrets go to the keychain when it is available."""

    def test_token_stored_in_keychain_not_in_file(self, manager, mock_keyring):
        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )

        raw = read_raw_config(manager)["default"]
        assert raw["token_in_keychain"] is True
        assert "token" not in raw
        assert (
            mock_keyring._store[("confluence-markdown", "default:token")] == "s3cret"
        )

    def test_load_resolves_secret_from_keychain(self, manager, mock_keyring):
        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )

        loaded = manager.load_config("default")
        assert loaded["token"] == "s3cret"
        assert "token_in_keychain" not in loaded

    def test_load_with_missing_keychain_entry(self, manager, mock_keyring):
        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )
        mock_keyring._store.clear()

        loaded = manager.load_config("default")
        assert "token" not in loaded
        assert loaded["base_url"] == "https://example.com"

    def test_delete_profile_removes_secrets(self, manager, mock_keyring):
        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )

        manager.delete_profile("default")
        assert mock_keyring._store == {}
        assert manager.load_config("default") is None


class TestPlaintextFallback:
    """Without a usable keychain, secrets fall back to plaintext + warning."""

    def test_keyring_unavailable_stores_plaintext(
        self, manager, monkeypatch, capsys
    ):
        monkeypatch.setattr(config_mod, "_KEYRING_AVAILABLE", False)

        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )

        raw = read_raw_config(manager)["default"]
        assert raw["token"] == "s3cret"
        assert "token_in_keychain" not in raw
        assert "WARNING" in capsys.readouterr().out

    def test_keyring_error_stores_plaintext(self, manager, mock_keyring, capsys):
        mock_keyring.set_password.side_effect = keyring.errors.KeyringError("locked")

        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )

        raw = read_raw_config(manager)["default"]
        assert raw["token"] == "s3cret"
        assert "token_in_keychain" not in raw
        assert "WARNING" in capsys.readouterr().out

    def test_plaintext_config_loads_without_keyring(self, manager, monkeypatch):
        monkeypatch.setattr(config_mod, "_KEYRING_AVAILABLE", False)

        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )
        loaded = manager.load_config("default")
        assert loaded["token"] == "s3cret"

    def test_keyring_error_on_load_returns_none_secret(
        self, manager, mock_keyring
    ):
        manager.save_config(
            {"base_url": "https://example.com", "token": "s3cret"}, "default"
        )
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("locked")

        loaded = manager.load_config("default")
        assert "token" not in loaded


class TestFilePermissions:
    """Config file must be user-only readable."""

    def test_config_file_mode_600(self, manager, mock_keyring):
        manager.save_config({"base_url": "https://example.com"}, "default")
        mode = manager.config_file.stat().st_mode & 0o777
        assert mode == 0o600
