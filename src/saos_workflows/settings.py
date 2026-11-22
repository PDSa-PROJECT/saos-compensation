"""Strict, independent controls for future judgment collection runs."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COLLECTION_CONFIG = ROOT / "configs/workflows/collection.yaml"


class CollectionSettings(BaseModel):
    """Freeze query and row-limit semantics without changing legacy settings."""

    model_config = ConfigDict(strict=True, extra="forbid")

    phrases: list[str] = Field(min_length=1)
    phrase_match: Literal["any", "all"]
    record_limit: int = Field(ge=0)

    @field_validator("phrases")
    @classmethod
    def unique_phrases(cls, phrases):
        """Reject duplicate or blank queries before collection begins.

        args:
            cls: Collection settings class.
            phrases: Ordered user-selected SAOS queries.

        returns:
            The unchanged list of valid phrases.
        """
        if any(not isinstance(phrase, str) or not phrase.strip() for phrase in phrases):
            raise ValueError("Each collection phrase must be nonblank")
        if len({phrase.strip().casefold() for phrase in phrases}) != len(phrases):
            raise ValueError("Collection phrases must be unique")
        return phrases


def load_collection_config(path=None):
    """Load only the selected collection controls from YAML.

    args:
        path: Explicit collection YAML file or the project default.

    returns:
        Validated dictionary without model or legacy runtime settings.
    """
    location = DEFAULT_COLLECTION_CONFIG if path is None else Path(path)
    with location.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict) or set(values) != set(CollectionSettings.model_fields):
        raise ValueError("Collection configuration requires phrases, phrase_match and record_limit only")
    return CollectionSettings.model_validate(values).model_dump()
