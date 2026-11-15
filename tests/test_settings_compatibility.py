"""Characterize configuration boundaries before migrating their implementation."""

from copy import deepcopy
from datetime import date
import json

import pytest
import yaml

from dataset.acquisition.settings import search_settings
from dataset.embeddings.encoding import validate_settings as validate_encoder
from dataset.embeddings.target_matching import validate_settings as validate_matcher
from dataset.extraction.model.configuration import load_config, read_config
from dataset.extraction.model.prompts import DEFAULTS
from dataset.preprocessing.io.configuration import validate_config


@pytest.mark.parametrize("number", [0, 1, 0.75])
def test_runtime_dictionary_preserves_yaml_values(config_directory, number):
    """Retain numeric types, text whitespace, ordering and pinned runtime defaults.

    args:
        config_directory: Editable acquisition YAML directory.
        number: Integer or float threshold that must not be coerced.

    returns:
        None.
    """
    basal = read_config(config_directory / "basal.yaml")
    basal.update(model=DEFAULTS["system_one"]["model"], device="cpu", minimum_probability=number)
    (config_directory / "basal.yaml").write_text(yaml.safe_dump(basal))
    features = {"metadata_fields": ["instance", "judgment_year"],
                "text_fields": {"damage": "  Szkoda?  ", "cause": "Przyczyna?"}}
    (config_directory / "features.yaml").write_text(yaml.safe_dump(features, sort_keys=False))
    api = read_config(config_directory / "api.yaml")
    api.update(max_gib=number, timeout=7, max_pages=-1, debug=True,
               download_path="tmp/compatibility")
    (config_directory / "api.yaml").write_text(yaml.safe_dump(api))
    targets = read_config(config_directory / "targets.yaml")
    targets["embedding"].update(device="cpu", batch_size=8)
    targets["embedding"]["minimum_cosine_similarity"] = number
    (config_directory / "targets.yaml").write_text(yaml.safe_dump(targets, sort_keys=False))
    overrides = {"max_pages": 2, "debug": False}
    expected = deepcopy(DEFAULTS)
    expected.update(api={**api, **overrides}, embedding=targets["embedding"],
                    target_patterns=targets["patterns"], fields=features["text_fields"],
                    metadata_fields=features["metadata_fields"], target_fields=["suma"])
    expected["system_one"].update(basal)
    expected["system_one"]["mode"] = "mps" if basal["device"] == "mps" else "eager"
    actual = load_config(config_directory, overrides)
    assert actual == expected
    # JSON preserves integer/float distinctions used in checkpoint/cache hashes.
    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert list(actual["fields"]) == list(features["text_fields"])
    assert list(actual["target_patterns"]) == list(targets["patterns"])
    assert overrides == {"max_pages": 2, "debug": False}


@pytest.mark.parametrize("key,value", [
    ("max_age_years", "10"), ("max_age_years", 10.0), ("max_age_years", True),
    ("max_pages", "1"), ("max_pages", 1.0), ("max_pages", False),
    ("max_gib", "1"), ("max_gib", True), ("max_gib", float("nan")),
    ("timeout", "20"), ("timeout", False), ("timeout", float("inf")),
    ("debug", "false"), ("debug", 0), ("download_path", "../outside"),
    ("download_path", "/outside"), ("download_path", "  "), ("extra", 1),
])
def test_acquisition_rejects_coercions_and_invalid_values(key, value):
    """Keep acquisition's strict types and relative-path boundary.

    args:
        key: Acquisition field to replace or add.
        value: Invalid input for that field.

    returns:
        None.
    """
    settings = load_config()["api"]
    with pytest.raises(ValueError):
        search_settings({**settings, key: value}, date(2024, 2, 29))


@pytest.mark.parametrize("key,value", [
    ("model", "  "), ("revision", 123), ("batch_size", "2"),
    ("batch_size", True), ("max_length", 3), ("max_length", 8.0),
    ("device", "automatic"),
])
def test_encoder_rejects_invalid_values(key, value):
    """Validate standalone encoder settings before loading weights.

    args:
        key: Encoder field to replace.
        value: Invalid input for that field.

    returns:
        None.
    """
    settings = load_config()["embedding"]
    with pytest.raises(ValueError):
        validate_encoder({**settings, key: value})


def test_encoder_ignores_extras_but_matcher_rejects_them():
    """Preserve the different standalone-encoder and matcher extra-key contracts.

    args:
        None.

    returns:
        None.
    """
    config = load_config()
    settings = {**config["embedding"], "unrelated": object()}
    assert validate_encoder(settings) is None
    with pytest.raises(ValueError):
        validate_matcher(settings, config["target_patterns"])


@pytest.mark.parametrize("value", [True, "0.7", -1, 1.1, float("nan"), float("inf")])
def test_matcher_rejects_invalid_thresholds(value):
    """Reject coercion and nonfinite or out-of-range matching thresholds.

    args:
        value: Invalid cosine threshold.

    returns:
        None.
    """
    config = load_config()
    with pytest.raises(ValueError):
        validate_matcher({**config["embedding"], "minimum_cosine_similarity": value},
                         config["target_patterns"])


@pytest.mark.parametrize("file,key,value", [
    ("basal.yaml", "minimum_probability", True),
    ("basal.yaml", "minimum_probability", "0.6"),
    ("basal.yaml", "maximum_leak_probability", float("nan")),
    ("basal.yaml", "amount_minimum_probability", 2),
    ("basal.yaml", "model", "unsupported"),
    ("basal.yaml", "device", "automatic"),
    ("features.yaml", "metadata_fields", ("instance",)),
    ("features.yaml", "text_fields", {"damage": "Szkoda?", "BadName": "Opis?"}),
])
def test_extraction_rejects_invalid_yaml(config_directory, file, key, value):
    """Preserve extraction validation without adding defaults for missing values.

    args:
        config_directory: Editable acquisition YAML directory.
        file: Configuration file to modify.
        key: Field to replace.
        value: Invalid value.

    returns:
        None.
    """
    settings = read_config(config_directory / file)
    settings[key] = value
    if isinstance(value, tuple):
        # Exercise the public loader with a YAML scalar rather than a sequence.
        settings[key] = "instance"
    (config_directory / file).write_text(yaml.safe_dump(settings))
    with pytest.raises(ValueError):
        load_config(config_directory)


@pytest.mark.parametrize("settings", [
    {}, {"feature_fields": []}, {"feature_fields": "judgment_year"},
    {"feature_fields": [1]}, {"feature_fields": ["damage", "damage"]},
    {"feature_fields": ["total"]}, {"feature_fields": ["instance"], "scaling": "none"},
])
def test_preprocessing_keeps_strict_allowlist(settings):
    """Reject malformed selections, labels, duplicates and policy overrides.

    args:
        settings: Invalid preprocessing configuration.

    returns:
        None.
    """
    with pytest.raises(ValueError):
        validate_config(settings)


def test_configuration_ignores_unrelated_ambient_sources(config_directory, monkeypatch, tmp_path):
    """Ignore unsupported variables and dotenv files outside the configured root.

    args:
        config_directory: Explicit YAML directory.
        monkeypatch: Scoped environment and directory changes.
        tmp_path: Directory containing a misleading dotenv file.

    returns:
        None.
    """
    expected = load_config(config_directory)
    (tmp_path / ".env").write_text("MAX_PAGES=999\nDEVICE=cuda\n")
    for name in ("MAX_PAGES", "max_pages", "SAOS_MAX_PAGES"):
        monkeypatch.setenv(name, "999")
    monkeypatch.setenv("DEVICE", "cuda")
    monkeypatch.chdir(tmp_path)
    assert load_config(config_directory) == expected
    assert validate_config({"feature_fields": ["damage", "instance"]}) == {
        "feature_fields": ["damage", "instance"]}
