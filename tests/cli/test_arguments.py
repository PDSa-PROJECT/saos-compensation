"""CLI overrides and separation between acquisition and processing controls."""

from datetime import date

import pytest

from dataset.acquisition.settings import load_config, search_settings
from dataset.cli import main as raw_cli
from dataset.cli import process as process_cli
from dataset.extraction.model.configuration import load_config as load_processing


@pytest.mark.parametrize("arguments,expected", [
    ([], {}), (["--max-pages", "2"], {"max_pages": 2}),
    (["--max-gib", "10"], {"max_gib": 10.0}), (["--no-debug"], {"debug": False}),
    (["--debug"], {"debug": True}),
    (["--download-path", "/tmp/raw/"], {"download_path": "/tmp/raw/"}),
    (["--download-path", "../raw"], {"download_path": "../raw"}),
    (["--max-age-years", "10", "--max-gib", "10", "--download-path", "tmp/test", "--debug", "--timeout", "60"],
     {"max_age_years": 10, "max_gib": 10.0, "download_path": "tmp/test", "debug": True, "timeout": 60.0}),
])
def test_raw_cli_overrides_only_supplied_settings(arguments, expected):
    """Preserve acquisition YAML defaults except explicitly supplied flags.

    args:
        arguments: Raw-download argument list.
        expected: Explicit overrides.

    returns:
        None.
    """
    options = vars(raw_cli.parse_arguments(arguments))
    assert options.pop("config_dir") is None
    assert options == expected
    assert load_config(overrides=options) == {**load_config(), **expected}


def test_raw_config_does_not_require_model_files(tmp_path):
    """Load a download-only directory containing no Basal or embedding configuration.

    args:
        tmp_path: Isolated raw configuration directory.

    returns:
        None.
    """
    import yaml

    settings = {**load_config(), "max_pages": -1}
    (tmp_path / "api.yaml").write_text(yaml.safe_dump(settings))
    assert load_config(tmp_path, {"max_pages": 1})["max_pages"] == 1
    start, end, _ = search_settings(load_config(), date(2024, 2, 29))
    assert (start, end) == (date(2014, 2, 28), date(2024, 2, 29))


@pytest.mark.parametrize("arguments,expected", [
    ([], {}), (["--input-path", "tmp/test"], {"input_path": "tmp/test"}),
    (["--output-path", "tmp/results", "--no-debug"], {"output_path": "tmp/results", "debug": False}),
    (["--input-path", "/tmp/raw/", "--output-path", "/tmp/processed/"],
     {"input_path": "/tmp/raw/", "output_path": "/tmp/processed/"}),
    (["--input-path", "../raw", "--output-path", "../processed"],
     {"input_path": "../raw", "output_path": "../processed"}),
])
def test_processing_cli_has_independent_settings(arguments, expected):
    """Keep local processing overrides separate from acquisition date/page flags.

    args:
        arguments: Processing argument list.
        expected: Explicit processing overrides.

    returns:
        None.
    """
    options = vars(process_cli.parse_arguments(arguments))
    assert options.pop("config_dir") is None
    assert options == expected
    config = load_processing(overrides=options)
    assert config["processing"] == {**load_processing()["processing"], **expected}
    assert "api" not in config


@pytest.mark.parametrize("flag", ["--max-age-years", "--download-path", "--max-pages"])
def test_processing_cli_rejects_download_flags(flag):
    """Reject acquisition options at the processing entry point.

    args:
        flag: Download-specific argument.

    returns:
        None.
    """
    with pytest.raises(SystemExit):
        process_cli.parse_arguments([flag, "1"])
