"""Shared YAML and repository-relative path validation."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def read_config(path):
    """Read a YAML mapping without applying application-specific defaults.

    args:
        path: YAML file to read.

    returns:
        Parsed configuration mapping.
    """
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    return value


def validate_path(value, name):
    """Require a nonempty path relative to the project root.

    args:
        value: Configured path string.
        name: Configuration key used in diagnostics.

    returns:
        None.
    """
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError(f"{name} must be relative to the project root")
