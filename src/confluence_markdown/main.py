#!/usr/bin/env python3
"""Compatibility wrapper for CLI entrypoint."""

from .cli import main
from .client import ConfluenceClient
from .config import ConfigManager

__all__ = ["main", "ConfluenceClient", "ConfigManager"]


if __name__ == "__main__":
    main()
