"""Verify the shared settings policy never adds configuration sources."""

import json

import pytest
from pydantic_settings import BaseSettings

from dataset.acquisition.settings import AcquisitionSettings
from dataset.embeddings.settings import EncoderSettings, TargetMatchingSettings, TargetSettings
from dataset.extraction.model.configuration import load_config, read_config
from dataset.extraction.model.settings import BasalSettings, FeatureSettings
from dataset.preprocessing.settings import PreprocessingSettings


def test_settings_ignore_environment_dotenv_and_secrets(monkeypatch, tmp_path):
    """Require explicit inputs even when BaseSettings ambient sources are populated.

    args:
        monkeypatch: Scoped environment and directory changes.
        tmp_path: Directory used as both a dotenv and secrets source.

    returns:
        None.
    """
    values = {"max_age_years": 10, "max_pages": 0, "max_gib": 1,
              "debug": True, "download_path": "tmp/", "timeout": 20}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAX_PAGES", "999")
    (tmp_path / ".env").write_text("MAX_PAGES=999\n")
    (tmp_path / "max_pages").write_text("999")
    settings = AcquisitionSettings(**values, _env_file=tmp_path / ".env",
                                   _secrets_dir=tmp_path)
    assert settings.model_dump() == values
    with pytest.raises(ValueError):
        AcquisitionSettings.from_mapping({key: value for key, value in values.items()
                                          if key != "max_pages"})
    with pytest.raises(ValueError):
        AcquisitionSettings.from_mapping({**values, "_env_file": str(tmp_path / ".env")})


@pytest.mark.parametrize("number", [0, 1, 1.5])
def test_acquisition_dump_preserves_numeric_types(number):
    """Prevent float coercion from altering serialized settings and cache identities.

    args:
        number: Valid integer or floating-point size limit.

    returns:
        None.
    """
    settings = AcquisitionSettings.from_mapping({
        "max_age_years": 10, "max_pages": 0, "max_gib": number,
        "debug": False, "download_path": "tmp/", "timeout": 20,
    })
    assert type(settings.model_dump()["max_gib"]) is type(number)


def test_target_settings_preserve_pattern_order_and_reject_control_keys():
    """Keep tie-breaking order and prevent nested Pydantic source overrides.

    args:
        None.

    returns:
        None.
    """
    config = load_config()
    values = {"embedding": config["embedding"], "patterns": config["target_patterns"]}
    dumped = TargetSettings.from_mapping(values).model_dump()
    assert dumped == values
    assert list(dumped["patterns"]) == list(values["patterns"])
    with pytest.raises(ValueError):
        TargetSettings.from_mapping({**values, "embedding": {
            **values["embedding"], "_env_file": "other.env",
        }})


@pytest.mark.parametrize("settings_class,file,section", [
    (AcquisitionSettings, "dataset/acquisition/api.yaml", None),
    (EncoderSettings, "dataset/acquisition/targets.yaml", "embedding"),
    (TargetMatchingSettings, "dataset/acquisition/targets.yaml", "embedding"),
    (TargetSettings, "dataset/acquisition/targets.yaml", None),
    (BasalSettings, "dataset/acquisition/basal.yaml", None),
    (FeatureSettings, "dataset/acquisition/features.yaml", None),
    (PreprocessingSettings, "training/model_input.yaml", None),
])
def test_settings_share_source_and_roundtrip_policy(
    settings_class, file, section, project_root, monkeypatch, tmp_path,
):
    """Keep every schema strict, source-explicit and serialization-compatible.

    args:
        settings_class: Concrete settings schema to exercise.
        file: Configuration path relative to configs/.
        section: Optional subsection for an encoder-only schema.
        project_root: Repository root containing configuration files.
        monkeypatch: Scoped environment and CLI replacements.
        tmp_path: Isolated dotenv and secrets directory.

    returns:
        None.
    """
    assert issubclass(settings_class, BaseSettings)
    values = read_config(project_root / "configs" / file)
    if section is not None:
        values = values[section]
    if settings_class is EncoderSettings:
        values = {key: values[key] for key in settings_class.model_fields}
    monkeypatch.setattr("sys.argv", ["get-data", "--unknown-setting"])
    monkeypatch.setenv("DEVICE", "cuda")
    (tmp_path / ".env").write_text("UNEXPECTED_SETTING=ignored\n")
    actual = settings_class(**values, _env_file=tmp_path / ".env", _secrets_dir=tmp_path)
    assert actual.model_dump() == values
    assert json.dumps(actual.model_dump(), sort_keys=True) == json.dumps(values, sort_keys=True)
    for key in values:
        partial = {name: value for name, value in values.items() if name != key}
        with pytest.raises(ValueError):
            settings_class.from_mapping(partial)
    for key in ("unexpected", "_env_file", "_cli_parse_args", "_secrets_dir"):
        with pytest.raises(ValueError):
            settings_class.from_mapping({**values, key: "ignored"})
