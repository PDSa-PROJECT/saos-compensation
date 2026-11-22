"""Basic collection configuration validation."""

import pytest

from saos_workflows.settings import CollectionSettings, load_collection_config


def test_collection_config_accepts_defaults_and_rejects_unknown_keys():
    """Keep the new collection settings separate and strict.

    args:
        None.
    returns:
        None.
    """
    assert load_collection_config() == {
        "phrases": ["zadośćuczynienie"], "phrase_match": "any", "record_limit": 100,
    }
    with pytest.raises(ValueError):
        CollectionSettings.model_validate({**load_collection_config(), "unexpected": True})
