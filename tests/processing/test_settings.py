"""Processing configuration boundaries independent of raw download controls."""

import pytest

from dataset.processing.settings import validate_settings


@pytest.mark.parametrize("overrides", [
    {"input_path": "../raw"}, {"output_path": "/processed"},
    {"input_path": "raw", "output_path": "raw/processed"},
    {"input_path": "raw/nested", "output_path": "raw"},
    {"max_gib": float("nan")}, {"max_gib": -1},
    {"timeout": 0}, {"timeout": float("inf")}, {"debug": "false"},
    {"max_pages": 1},
])
def test_invalid_processing_controls_are_rejected(overrides):
    """Reject overlapping paths, download flags and malformed runtime values.

    args:
        overrides: Invalid settings for one boundary case.

    returns:
        None.
    """
    settings = {"input_path": "raw", "output_path": "processed", "max_gib": 0, "debug": False, "timeout": 30}
    with pytest.raises(ValueError):
        validate_settings({**settings, **overrides})
