"""Configuration manager for credentials."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Manages configuration file for Confluence credentials."""

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "confluence-markdown"
        self.config_file = self.config_dir / "config.json"

    def ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (user read/write only)
        os.chmod(self.config_dir, 0o700)

    def save_config(self, config: Dict[str, Any], profile: str = "default"):
        """Save configuration to file."""
        self.ensure_config_dir()

        # Load existing config or create new
        existing_config = self.load_all_configs()
        existing_config[profile] = config

        # Write config file with restrictive permissions
        with open(self.config_file, "w") as f:
            json.dump(existing_config, f, indent=2)
        os.chmod(self.config_file, 0o600)

        print(f"✅ Configuration saved to {self.config_file} (profile: {profile})")

    def load_config(self, profile: str = "default") -> Optional[Dict[str, Any]]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return None

        try:
            with open(self.config_file, "r") as f:
                all_configs = json.load(f)
                return all_configs.get(profile)
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
        """Delete a configuration profile."""
        configs = self.load_all_configs()
        if profile in configs:
            del configs[profile]
            with open(self.config_file, "w") as f:
                json.dump(configs, f, indent=2)
            print(f"✅ Profile '{profile}' deleted")
        else:
            print(f"❌ Profile '{profile}' not found")
