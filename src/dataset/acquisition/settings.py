"""Acquisition configuration and inclusive date bounds."""

from calendar import monthrange
from datetime import date
from pathlib import Path

from ..configuration import ROOT, read_config, validate_path


def search_settings(config, today=None):
    """
    Validate acquisition settings and derive inclusive judgment-date bounds.

    args:
        config: Effective pipeline or acquisition settings.
        today: Date used to anchor the acquisition range.

    returns:
        Start date, end date and effective query parameters.
    """
    if not isinstance(config, dict) or set(config) != {
        "max_age_years",
        "max_pages",
        "max_gib",
        "debug",
        "download_path",
        "timeout",
    }:
        raise ValueError(
            "api.yaml requires max_age_years, max_pages, max_gib, debug, download_path and timeout"
        )
    if type(config["max_gib"]) not in (int, float) or not 0 <= config[
        "max_gib"
    ] < float("inf"):
        raise ValueError("max_gib must be a nonnegative finite number")
    if type(config["timeout"]) not in (int, float) or not 0 < config["timeout"] < float(
        "inf"
    ):
        raise ValueError("timeout must be a positive finite number")
    if type(config["debug"]) is not bool:
        raise ValueError("debug must be true or false")
    years, limit = config["max_age_years"], config["max_pages"]
    if type(years) is not int or years <= 0 or type(limit) is not int or limit < 0:
        raise ValueError("max_age_years must be positive and max_pages nonnegative")
    validate_path(config["download_path"], "download_path")
    end = today or date.today()
    if years >= end.year:
        raise ValueError("max_age_years exceeds the supported date range")
    start = end.replace(
        year=end.year - years,
        day=min(end.day, monthrange(end.year - years, end.month)[1]),
    )
    params = {
        "pageSize": 100,
        "pageNumber": 0,
        "judgmentStartDate": start.isoformat(),
        "judgmentEndDate": end.isoformat(),
    }
    return start, end, params


def load_config(directory=None, overrides=None):
    """Load only acquisition YAML and apply explicit download overrides.

    args:
        directory: Directory containing api.yaml or None for the repository default.
        overrides: Explicit CLI acquisition values.

    returns:
        Validated download settings without model configuration.
    """
    directory = Path(directory) if directory is not None else ROOT / "configs/dataset/acquisition"
    settings = read_config(directory / "api.yaml")
    settings.update(overrides or {})
    search_settings(settings)
    return settings
