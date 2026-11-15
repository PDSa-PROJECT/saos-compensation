"""Runtime source priority and typed environment parsing without model inference."""

import pytest

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
