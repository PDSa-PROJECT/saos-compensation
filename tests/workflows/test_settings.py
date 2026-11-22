"""Workflow configuration stays independent of legacy CLI settings."""

import json

import pytest
import yaml

from saos_workflows.cli import main
from saos_workflows.settings import CollectionSettings, load_collection_config


def test_default_collection_controls_are_explicit_and_valid(capsys):
    """Expose the validated YAML without starting a pipeline or a model.

    args:
        capsys: Captured CLI output.

    returns:
        None.
    """
    expected = {"phrases": ["zadośćuczynienie"], "phrase_match": "any", "record_limit": 100}
    assert load_collection_config() == expected
    assert main([]) == 0
    assert json.loads(capsys.readouterr().out) == expected


@pytest.mark.parametrize("values", [
    {"phrases": [], "phrase_match": "any", "record_limit": 1},
    {"phrases": ["A", " a "], "phrase_match": "any", "record_limit": 1},
    {"phrases": [" "], "phrase_match": "any", "record_limit": 1},
    {"phrases": ["A"], "phrase_match": "either", "record_limit": 1},
    {"phrases": ["A"], "phrase_match": "all", "record_limit": -1},
    {"phrases": ["A"], "phrase_match": "all", "record_limit": True},
    {"phrases": ["A"], "phrase_match": "all", "record_limit": 1, "unknown": True},
])
def test_collection_rejects_invalid_controls(tmp_path, values):
    """Fail on ambiguous or extra experiment fields before any acquisition.

    args:
        tmp_path: Isolated configuration directory.
        values: Invalid configuration mapping.

    returns:
        None.
    """
    path = tmp_path / "collection.yaml"
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    with pytest.raises(ValueError):
        load_collection_config(path)


def test_explicit_collection_config_does_not_change_defaults(tmp_path, capsys):
    """Allow a separate controlled experiment without editing package defaults.

    args:
        tmp_path: Isolated configuration directory.
        capsys: Captured CLI output.

    returns:
        None.
    """
    values = {"phrases": ["zadośćuczynienie", "odszkodowanie"], "phrase_match": "all", "record_limit": 0}
    path = tmp_path / "collection.yaml"
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    assert CollectionSettings.model_validate(values).model_dump() == values
    assert main(["--collection-config", str(path)]) == 0
    assert json.loads(capsys.readouterr().out) == values
