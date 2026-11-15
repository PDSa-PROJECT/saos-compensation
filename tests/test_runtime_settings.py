"""Runtime source priority and typed environment parsing without model inference."""

from pathlib import Path

import pytest
import yaml

from dataset.extraction.model.configuration import load_config, read_config
from dataset.settings import RuntimeSettings


@pytest.fixture
def runtime_environment(monkeypatch, tmp_path):
    """Isolate supported environment names and use only a temporary dotenv file.

    args:
        monkeypatch: Scoped environment replacements.
        tmp_path: Directory for a non-secret test dotenv file.

    returns:
        Path to the isolated dotenv file.
    """
    for name in RuntimeSettings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(name, raising=False)
    return tmp_path / ".env"


def test_runtime_source_precedence(runtime_environment, monkeypatch):
    """Apply CLI then environment then dotenv then YAML then runtime defaults.

    args:
        runtime_environment: Isolated dotenv path.
        monkeypatch: Scoped environment replacements.

    returns:
        None.
    """
    runtime_environment.write_text("ACQUISITION_TIMEOUT=40\nACQUISITION_DEBUG=false\n")
    monkeypatch.setenv("ACQUISITION_TIMEOUT", "60")
    settings = RuntimeSettings(_env_file=runtime_environment)
    merged = settings.merge("acquisition", {"timeout": 10, "max_pages": 2})
    assert merged["timeout"] == 60
    assert merged["debug"] is False
    assert merged["max_pages"] == 2
    assert merged["max_gib"] == 0.5
    cli = RuntimeSettings(acquisition_timeout=80, _env_file=runtime_environment)
    assert cli.merge("acquisition", {"timeout": 10})["timeout"] == 80


def test_yaml_runtime_values_remain_fallbacks(runtime_environment):
    """Preserve custom legacy YAML values when no higher-priority source exists.

    args:
        runtime_environment: Missing dotenv path.

    returns:
        None.
    """
    settings = RuntimeSettings(_env_file=runtime_environment)
    assert settings.values_for("basal", explicit_only=True) == {}
    assert settings.merge("basal", {"device": "cpu", "model": "yaml-model"}) == {
        "device": "cpu", "model": "yaml-model",
    }


@pytest.mark.parametrize("name,value", [
    ("ACQUISITION_DEBUG", "maybe"), ("ACQUISITION_TIMEOUT", "0"),
    ("ACQUISITION_TIMEOUT", "nan"), ("ACQUISITION_MAX_GIB", "-1"),
    ("ACQUISITION_MAX_GIB", "inf"), ("EMBEDDING_BATCH_SIZE", "0"),
    ("BASAL_DEVICE", "automatic"), ("EMBEDDING_MODEL", ""),
])
def test_invalid_runtime_values_fail(runtime_environment, monkeypatch, name, value):
    """Reject malformed recognized environment values instead of falling back.

    args:
        runtime_environment: Missing dotenv path.
        monkeypatch: Scoped environment replacements.
        name: Supported variable to set.
        value: Invalid environment value.

    returns:
        None.
    """
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        RuntimeSettings(_env_file=runtime_environment)


def test_unrelated_dotenv_values_and_secrets_are_ignored(runtime_environment, tmp_path):
    """Read only supported runtime fields without enabling secrets or automatic CLI.

    args:
        runtime_environment: Isolated dotenv path.
        tmp_path: Directory containing a misleading secrets file.

    returns:
        None.
    """
    runtime_environment.write_text("UNRELATED_SETTING=ignored\nBASAL_DEVICE=cpu\n")
    (tmp_path / "embedding_device").write_text("cuda")
    settings = RuntimeSettings(_env_file=runtime_environment, _secrets_dir=tmp_path)
    assert settings.basal_device == "cpu"
    assert settings.embedding_device == "mps"


def test_cli_can_override_invalid_environment(runtime_environment, monkeypatch):
    """Validate the highest-priority value rather than a shadowed invalid source.

    args:
        runtime_environment: Missing dotenv path.
        monkeypatch: Scoped environment replacements.

    returns:
        None.
    """
    monkeypatch.setenv("ACQUISITION_TIMEOUT", "invalid")
    settings = RuntimeSettings(acquisition_timeout=30, _env_file=runtime_environment)
    assert settings.acquisition_timeout == 30


def test_loader_merges_yaml_dotenv_environment_and_cli(config_directory, monkeypatch):
    """Apply the agreed source priority to the complete normalized configuration.

    args:
        config_directory: Editable acquisition YAML directory.
        monkeypatch: Scoped process environment overrides.

    returns:
        None.
    """
    path = config_directory / "api.yaml"
    api = read_config(path)
    api.update(timeout=5, max_gib=0.1, download_path="tmp/yaml", debug=True)
    path.write_text(yaml.safe_dump(api))
    Path(RuntimeSettings.model_config["env_file"]).write_text(
        "ACQUISITION_TIMEOUT=40\nACQUISITION_MAX_GIB=2\n"
        "ACQUISITION_DOWNLOAD_PATH=tmp/dotenv\nACQUISITION_DEBUG=false\n"
        "BASAL_DEVICE=cpu\nBASAL_MODEL=Remek/basal-2.0-4.5B\n"
        "EMBEDDING_DEVICE=cpu\nEMBEDDING_BATCH_SIZE=4\n"
        "EMBEDDING_MODEL=example/encoder\nEMBEDDING_REVISION=pinned-example\n"
    )
    monkeypatch.setenv("ACQUISITION_TIMEOUT", "60")
    monkeypatch.setenv("BASAL_MODEL", "Remek/basal-2.0-mini")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "8")
    config = load_config(config_directory, {"timeout": 80, "debug": True})
    assert config["api"] == {**api, "timeout": 80, "debug": True,
                             "max_gib": 2, "download_path": "tmp/dotenv"}
    assert config["system_one"]["model"] == "Remek/basal-2.0-mini"
    assert config["system_one"]["device"] == "cpu"
    assert config["system_one"]["mode"] == "eager"
    assert config["embedding"]["device"] == "cpu"
    assert config["embedding"]["batch_size"] == 8
    assert config["embedding"]["model"] == "example/encoder"
    assert config["embedding"]["revision"] == "pinned-example"


def test_loader_cli_overrides_invalid_lower_sources(config_directory, monkeypatch):
    """Keep explicit CLI values usable even when lower-priority values are invalid.

    args:
        config_directory: Editable acquisition YAML directory.
        monkeypatch: Scoped process environment overrides.

    returns:
        None.
    """
    monkeypatch.setenv("ACQUISITION_TIMEOUT", "invalid")
    monkeypatch.setenv("ACQUISITION_DEBUG", "invalid")
    config = load_config(config_directory, {"timeout": 30, "debug": False})
    assert config["api"]["timeout"] == 30
    assert config["api"]["debug"] is False


def test_loader_uses_global_not_working_directory_dotenv(config_directory, monkeypatch, tmp_path):
    """Keep the root dotenv location independent of config directory and cwd.

    args:
        config_directory: Explicit YAML directory distinct from the dotenv root.
        monkeypatch: Scoped working-directory change.
        tmp_path: Directory containing a misleading cwd dotenv file.

    returns:
        None.
    """
    Path(RuntimeSettings.model_config["env_file"]).write_text("ACQUISITION_TIMEOUT=45\n")
    (tmp_path / ".env").write_text("ACQUISITION_TIMEOUT=999\n")
    monkeypatch.chdir(tmp_path)
    assert load_config(config_directory)["api"]["timeout"] == 45


def test_experiment_fields_are_not_environment_overrides(config_directory, monkeypatch):
    """Keep feature lists, date bounds, windows and thresholds YAML-controlled.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped process environment overrides.

    returns:
        None.
    """
    expected = load_config(config_directory)
    for name in (
        "ACQUISITION_MAX_AGE_YEARS", "ACQUISITION_MAX_PAGES", "EMBEDDING_MAX_LENGTH",
        "EMBEDDING_MINIMUM_COSINE_SIMILARITY", "BASAL_MINIMUM_PROBABILITY",
        "FEATURE_FIELDS", "TEXT_FIELDS", "CANDIDATE_KEYWORDS", "PATTERNS",
    ):
        monkeypatch.setenv(name, "invalid")
    assert load_config(config_directory) == expected


def test_changed_embedding_model_requires_explicit_revision(config_directory, monkeypatch):
    """Avoid reusing the previous encoder's pinned revision for another model.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped model/revision overrides.

    returns:
        None.
    """
    original = load_config(config_directory)["embedding"]
    monkeypatch.setenv("EMBEDDING_MODEL", original["model"])
    assert load_config(config_directory)["embedding"]["revision"] == original["revision"]
    monkeypatch.setenv("EMBEDDING_MODEL", "example/another-encoder")
    with pytest.raises(ValueError, match="EMBEDDING_REVISION"):
        load_config(config_directory)
    monkeypatch.setenv("EMBEDDING_REVISION", "another-pinned-revision")
    assert load_config(config_directory)["embedding"]["revision"] == "another-pinned-revision"


@pytest.mark.parametrize("name,value", [
    ("BASAL_MODEL", "unsupported"), ("ACQUISITION_DOWNLOAD_PATH", "../outside"),
    ("EMBEDDING_REVISION", ""),
])
def test_loader_validates_runtime_overrides(config_directory, monkeypatch, name, value):
    """Validate merged runtime values before downloads or model startup.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped environment replacements.
        name: Runtime variable to set.
        value: Invalid value for that variable.

    returns:
        None.
    """
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        load_config(config_directory)


def test_example_env_preserves_runtime_defaults(project_root):
    """Keep copying the non-secret example equivalent to an absent dotenv file.

    args:
        project_root: Repository root containing the committed example.

    returns:
        None.
    """
    default = RuntimeSettings(_env_file=None)
    example = RuntimeSettings(_env_file=project_root / ".env.example")
    assert example.model_dump() == default.model_dump()


def test_runtime_changes_preserve_or_invalidate_checkpoint_as_before(
    config_directory, monkeypatch, tmp_path,
):
    """Allow operational overrides but reject changed model/device signatures.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped checkpoint root and environment changes.
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
