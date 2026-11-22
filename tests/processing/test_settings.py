"""Processing configuration boundaries independent of raw download controls."""

import pytest

from saos_dataset.processing.settings import validate_settings


@pytest.mark.parametrize("overrides", [
    {"input_path": ""}, {"output_path": " "}, {"output_path": "\0"}, {"input_path": None},
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


@pytest.mark.parametrize("alias", ["absolute", "parent", "symlink"])
def test_processing_rejects_resolved_path_overlap(monkeypatch, tmp_path, alias):
    """Reject overlapping locations even when their configured strings differ.

    args:
        monkeypatch: Scoped launch-directory override.
        tmp_path: Isolated project root.
        alias: Alternate spelling of the input directory.

    returns:
        None.
    """
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / "raw"
    raw.mkdir()
    if alias == "absolute":
        output = str(raw / "processed")
    elif alias == "parent":
        output = "other/../raw/processed"
    else:
        (tmp_path / "alias").symlink_to(raw, target_is_directory=True)
        output = "alias/processed"
    config = {"input_path": "raw", "output_path": output, "max_gib": 0, "debug": False, "timeout": 30}
    with pytest.raises(ValueError, match="must not overlap"):
        validate_settings(config)
