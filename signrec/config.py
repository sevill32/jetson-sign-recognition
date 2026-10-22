"""Configuration loader for the sign recognition system."""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(ROOT, "config", "config.json")


def load_config(path=None):
    """Load a JSON configuration file and return it as a dict."""
    if path is None:
        path = DEFAULT_CONFIG_PATH
    with open(path, "r") as handle:
        config = json.load(handle)
    return config


def resolve_path(path):
    """Resolve a possibly relative path against the repository root."""
    if os.path.isabs(path):
        return path
    return os.path.join(ROOT, path)


def ensure_dir(path):
    """Create a directory (and parents) if it does not exist."""
    if path:
        os.makedirs(path, exist_ok=True)
    return path
