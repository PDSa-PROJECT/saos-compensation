import pytest

from saos_dataset.acquisition.settings import search_settings


CONFIG = {
    "max_age_years": 10,
    "max_pages": 0,
    "max_gib": 0,
    "debug": False,
    "download_path": "tmp/",
    "timeout": 30,
}

@pytest.mark.parametrize(
    "change",
    [
        {"max_age_years": True},
        {"max_age_years": 3000},
        {"max_pages": -1},
        {"debug": "true"},
        {"download_path": ""},
        {"download_path": "\0"},
        {"download_path": None},
        {"max_gib": -1},
        {"max_gib": True},
        {"max_gib": float("nan")},
        {"timeout": 0},
        {"timeout": float("inf")},
    ],
)
def test_invalid_config_is_rejected(change):
    """
    Verify invalid config is rejected.

    args:
        change: Configuration change under examination.

    returns:
        None.
    """
    with pytest.raises(ValueError):
        search_settings({**CONFIG, **change})
