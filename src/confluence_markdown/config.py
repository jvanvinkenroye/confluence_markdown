"""Configuration manager for credentials."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import keyring
    import keyring.errors

    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

_KEYRING_SERVICE = "confluence-markdown"


class ConfigManager:
    """Manages configuration file for Confluence credentials."""

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "confluence-markdown"
        self.config_file = self.config_dir / "config.json"

    # ------------------------------------------------------------------
    # Keychain helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _keychain_key(profile: str, field: str) -> str:
        return f"{profile}:{field}"

    def _save_secret(self, profile: str, field: str, value: str) -> bool:
        """Store a secret in the system keychain. Returns True on success."""
        if not _KEYRING_AVAILABLE:
            return False
        try:
            keyring.set_password(
                _KEYRING_SERVICE, self._keychain_key(profile, field), value
            )
            return True
        except keyring.errors.KeyringError:
            return False

    def _load_secret(self, profile: str, field: str) -> Optional[str]:
        """Retrieve a secret from the system keychain."""
        if not _KEYRING_AVAILABLE:
            return None
        try:
            return keyring.get_password(
                _KEYRING_SERVICE, self._keychain_key(profile, field)
            )
        except keyring.errors.KeyringError:
            return None

    def _delete_secret(self, profile: str, field: str) -> None:
        if not _KEYRING_AVAILABLE:
            return
        try:
            keyring.delete_password(
                _KEYRING_SERVICE, self._keychain_key(profile, field)
            )
        except keyring.errors.KeyringError:
            pass

    def ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (user read/write only)
        os.chmod(self.config_dir, 0o700)

    def save_config(self, config: Dict[str, Any], profile: str = "default"):
        """Save configuration to file, storing secrets in the system keychain."""
        self.ensure_config_dir()

        file_config = dict(config)

        for field in ("token", "password"):
            value = file_config.pop(field, None)
            if value:
                if _KEYRING_AVAILABLE and self._save_secret(profile, field, value):
                    file_config[f"{field}_in_keychain"] = True
                else:
                    print(
                        f"WARNING: System keychain unavailable — storing {field} as "
                        "plaintext in config file. Install a keyring backend to avoid this."
                    )
                    file_config[field] = value

        existing_config = self.load_all_configs()
        existing_config[profile] = file_config

        with open(self.config_file, "w") as f:
            json.dump(existing_config, f, indent=2)
        os.chmod(self.config_file, 0o600)

        keychain_note = " (secrets stored in system keychain)" if _KEYRING_AVAILABLE else ""
        print(f"Configuration saved to {self.config_file} (profile: {profile}){keychain_note}")

    def load_config(self, profile: str = "default") -> Optional[Dict[str, Any]]:
        """Load configuration from file, resolving secrets from the system keychain."""
        if not self.config_file.exists():
            return None

        try:
            with open(self.config_file, "r") as f:
                all_configs = json.load(f)
            config = all_configs.get(profile)
            if config is None:
                return None

            for field in ("token", "password"):
                if config.pop(f"{field}_in_keychain", False):
                    secret = self._load_secret(profile, field)
                    if secret:
                        config[field] = secret

            return config
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
            return None

    def load_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load all configuration profiles."""
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def list_profiles(self) -> list:
        """List all available configuration profiles."""
        configs = self.load_all_configs()
        return list(configs.keys())

    def delete_profile(self, profile: str):
        """Delete a configuration profile and its keychain secrets."""
        configs = self.load_all_configs()
        if profile in configs:
            for field in ("token", "password"):
                self._delete_secret(profile, field)
            del configs[profile]
            with open(self.config_file, "w") as f:
                json.dump(configs, f, indent=2)
            print(f"Profile '{profile}' deleted")
        else:
            print(f"Profile '{profile}' not found")

    def get_space_config(self, profile: str, space_key: str) -> Dict[str, Any]:
        """
        Get configuration for a specific space, merged with profile defaults.

        Config structure:
        {
            "default": {
                "base_url": "...",
                "username": "...",
                "token": "...",
                "editor": "vim",
                "table_format": "markdown",
                "spaces": {
                    "DOCS": {"editor": "code", "table_format": "yaml"},
                    "WIKI": {"editor": "nano"}
                }
            }
        }
        """
        profile_config = self.load_config(profile) or {}

        # Start with profile-level settings (excluding 'spaces')
        merged = {k: v for k, v in profile_config.items() if k != "spaces"}

        # Merge space-specific settings if available
        spaces_config = profile_config.get("spaces", {})
        if space_key and space_key in spaces_config:
            merged.update(spaces_config[space_key])

        return merged

    def save_space_config(
        self, profile: str, space_key: str, space_settings: Dict[str, Any]
    ):
        """Save space-specific configuration."""
        configs = self.load_all_configs()
        if profile not in configs:
            configs[profile] = {}

        if "spaces" not in configs[profile]:
            configs[profile]["spaces"] = {}

        configs[profile]["spaces"][space_key] = space_settings

        self.ensure_config_dir()
        with open(self.config_file, "w") as f:
            json.dump(configs, f, indent=2)
        os.chmod(self.config_file, 0o600)

        print(f"✅ Space config saved for {space_key} (profile: {profile})")
