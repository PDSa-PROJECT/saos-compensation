"""Verify the shared settings policy never adds configuration sources."""

import pytest

from dataset.acquisition.settings import AcquisitionSettings
from dataset.embeddings.settings import TargetSettings
from dataset.extraction.model.configuration import load_config


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
