"""Basic coverage for settings sources, model overrides and checkpoint compatibility."""

from pathlib import Path

import pytest
import yaml

from dataset.extraction.model.configuration import load_config, read_config
from dataset.settings import RuntimeSettings


def test_source_precedence(config_directory, monkeypatch):
    """Prefer CLI over environment, dotenv and YAML, in that order.

    args:
        config_directory: Editable acquisition YAML directory.
        monkeypatch: Scoped environment overrides.

    returns:
        None.
    """
    path = config_directory / "api.yaml"
    api = {**read_config(path), "timeout": 5}
    path.write_text(yaml.safe_dump(api))
    assert load_config(config_directory)["api"]["timeout"] == 5
    Path(RuntimeSettings.model_config["env_file"]).write_text(
        "ACQUISITION_TIMEOUT=40\nACQUISITION_DEBUG=false\n"
    )
    assert load_config(config_directory)["api"]["timeout"] == 40
    assert load_config(config_directory)["api"]["debug"] is False
    monkeypatch.setenv("ACQUISITION_TIMEOUT", "60")
    assert load_config(config_directory)["api"]["timeout"] == 60
    assert load_config(config_directory, {"timeout": 80})["api"]["timeout"] == 80


def test_model_overrides(config_directory, monkeypatch):
    """Override both models and require a revision for a changed embedding model.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped model/revision overrides.

    returns:
        None.
    """
    monkeypatch.setenv("BASAL_MODEL", "Remek/basal-2.0-mini")
    monkeypatch.setenv("EMBEDDING_MODEL", "example/encoder")
    with pytest.raises(ValueError, match="EMBEDDING_REVISION"):
        load_config(config_directory)
    monkeypatch.setenv("EMBEDDING_REVISION", "pinned-example")
    config = load_config(config_directory)
    assert config["system_one"]["model"] == "Remek/basal-2.0-mini"
    assert config["embedding"]["model"] == "example/encoder"
    assert config["embedding"]["revision"] == "pinned-example"


def test_invalid_runtime_value(config_directory, monkeypatch):
    """Reject malformed environment values before acquisition starts.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped environment overrides.

    returns:
        None.
    """
    monkeypatch.setenv("ACQUISITION_TIMEOUT", "invalid")
    with pytest.raises(ValueError):
        load_config(config_directory)


def test_example_env_preserves_defaults(project_root):
    """Keep the example dotenv equivalent to built-in runtime defaults.

    args:
        project_root: Repository root containing the non-secret example.

    returns:
        None.
    """
    assert RuntimeSettings(_env_file=project_root / ".env.example").model_dump() == (
        RuntimeSettings(_env_file=None).model_dump()
    )


def test_checkpoint_compatibility(config_directory, monkeypatch, tmp_path):
    """Allow operational changes but reject a different model/device signature.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped checkpoint root and environment overrides.
        tmp_path: Isolated checkpoint output root.

    returns:
        None.
    """
    from dataset.storage import checkpoints

    monkeypatch.setattr(checkpoints, "ROOT", tmp_path)
    overrides = {"download_path": "dataset"}
    config = load_config(config_directory, overrides)
    checkpoint = checkpoints.load_checkpoint(config)
    checkpoints.save_checkpoint(tmp_path / "dataset", checkpoint)
    monkeypatch.setenv("ACQUISITION_TIMEOUT", "99")
    monkeypatch.setenv("ACQUISITION_DEBUG", "false")
    assert checkpoints.load_checkpoint(load_config(config_directory, overrides)) == checkpoint
    device = "cpu" if config["system_one"]["device"] != "cpu" else "mps"
    monkeypatch.setenv("BASAL_DEVICE", device)
    with pytest.raises(ValueError, match="Extraction settings changed"):
        checkpoints.load_checkpoint(load_config(config_directory, overrides))
