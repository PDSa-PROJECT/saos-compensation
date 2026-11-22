"""Validate the ordered allowlist of original model input fields."""

from pathlib import Path

import yaml

from ..settings import PreprocessingSettings


def validate_config(settings):
    """Validate feature selection without accepting preprocessing overrides.

    args:
        settings: Mapping containing only feature_fields, an ordered name list.

    returns:
        Independent validated feature selection.
    """
    return PreprocessingSettings.from_mapping(settings).model_dump()


def validate_scaling(settings):
    """Check internal numeric transformation choices.

    args:
        settings: Numeric or target policy mapping supplied by implementation code.

    returns:
        None.
    """
    if settings["transform"] not in ("identity", "log1p"):
        raise ValueError("transform must be identity or log1p")
    if settings["scaling"] not in ("none", "standard", "robust"):
        raise ValueError("scaling must be none, standard or robust")


def load_config(path):
    """Read the ordered model feature allowlist from YAML.

    args:
        path: Model input YAML path.

    returns:
        Validated feature selection without transformation settings.
    """
    return validate_config(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
