"""Typed model-input selection without configurable transformation policies."""

from pydantic import field_validator

from saos_dataset.settings import Settings
from .transforms.rules import FIELD_RULES, TEXT_FIELDS


class PreprocessingSettings(Settings):
    """An ordered allowlist of original predictors, separate from fitted state."""

    feature_fields: list[str]

    @field_validator("feature_fields")
    @classmethod
    def selected_predictors(cls, value):
        """Require unique supported predictor names and preserve their order.

        args:
            cls: Preprocessing settings class.
            value: Strictly parsed original predictor names.

        returns:
            The unchanged ordered allowlist.
        """
        if not value:
            raise ValueError("feature_fields must be a nonempty list of names")
        if len(value) != len(set(value)):
            raise ValueError("feature_fields cannot contain duplicates")
        for field in value:
            if field not in FIELD_RULES and field not in TEXT_FIELDS:
                raise ValueError(f"Unsupported predictor: {field}")
        return value
