"""Typed extraction settings; prompts and technical defaults remain code-controlled."""

import re
from typing import Literal

from pydantic import field_validator

from saos_dataset.settings import Device, NonblankString, Probability, Settings
from .prompts import METADATA_FIELDS

MODEL_REVISIONS = {
    "Remek/basal-2.0-mini": "cb81b32ce89b0b87e62fcdad28f0435e25c953f3",
    "Remek/basal-2.0-4.5B": "e5ba9149760d99b73b1963d8e0ccf948b58afacb",
}


class BasalSettings(Settings):
    """The supported model/device and existing extraction/review thresholds."""

    model: Literal["Remek/basal-2.0-mini", "Remek/basal-2.0-4.5B"]
    device: Device
    minimum_probability: Probability
    maximum_leak_probability: Probability
    amount_minimum_probability: Probability


class FeatureSettings(Settings):
    """Selected metadata and ordered source-extraction questions."""

    metadata_fields: list[str]
    text_fields: dict[str, NonblankString]

    @field_validator("metadata_fields")
    @classmethod
    def supported_metadata(cls, value):
        """Require unique supported enrichments without reordering selections.

        args:
            cls: Feature settings class.
            value: Ordered metadata field names.

        returns:
            The unchanged validated selection.
        """
        if len(value) != len(set(value)) or any(field not in METADATA_FIELDS for field in value):
            raise ValueError("Invalid metadata_fields")
        return value

    @field_validator("text_fields")
    @classmethod
    def source_questions(cls, value):
        """Require damage and valid English field identifiers with source questions.

        args:
            cls: Feature settings class.
            value: Ordered mapping of feature names to nonblank Polish questions.

        returns:
            The original mapping without changing names or question text.
        """
        if not value or any(
            re.fullmatch(r"[a-z][a-z0-9_]*", name) is None or name in METADATA_FIELDS
            for name in value
        ):
            raise ValueError("text_fields must be nonempty and map field names to nonempty questions")
        if "damage" not in value:
            raise ValueError("text_fields must include damage")
        return value
