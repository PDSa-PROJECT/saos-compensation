"""Typed encoder and target-matching settings, independent of model loading."""

from pydantic import Field, field_validator

from ..settings import Device, NonblankString, Probability, Settings

TARGET_CLASSES = ("judgment", "request")
EXCLUDED_CLASSES = ("prior_payment", "procedural_costs", "mixed", "other_payments")
PATTERN_CLASSES = TARGET_CLASSES + EXCLUDED_CLASSES + ("judgment-denial",)


class EncoderSettings(Settings):
    """The reusable encoder's five settings; callers may project larger mappings."""

    model: NonblankString
    revision: NonblankString
    device: Device
    batch_size: int = Field(gt=0)
    max_length: int = Field(ge=4)


ENCODER_SETTINGS = tuple(EncoderSettings.model_fields)


class TargetMatchingSettings(EncoderSettings):
    """Encoder settings plus strict role eligibility and cosine admission settings."""

    minimum_cosine_similarity: Probability
    context_words_before: int = Field(ge=0)
    context_words_after: int = Field(ge=0)
    candidate_keywords: dict[str, list[NonblankString]]

    @field_validator("candidate_keywords")
    @classmethod
    def keyword_groups(cls, value):
        """Require the existing monetary keyword groups and at least one stem.

        args:
            cls: Target matching settings class.
            value: Parsed role-to-stem mapping, preserving configured order.

        returns:
            The unchanged validated keyword mapping.
        """
        groups = {*TARGET_CLASSES, *EXCLUDED_CLASSES, "shared"}
        if set(value) != groups:
            raise ValueError(f"candidate_keywords requires {sorted(groups)} groups")
        if not any(value.values()):
            raise ValueError("candidate_keywords requires at least one nonempty group")
        return value


class TargetSettings(Settings):
    """The two sections of targets.yaml, with original pattern ordering intact."""

    embedding: TargetMatchingSettings
    patterns: dict[str, list[NonblankString]]

    @field_validator("embedding", mode="before")
    @classmethod
    def explicit_embedding(cls, value):
        """Validate nested mappings before BaseSettings can consume control keys.

        args:
            cls: Target file settings class.
            value: Raw embedding mapping.

        returns:
            Validated target-matching settings.
        """
        return TargetMatchingSettings.from_mapping(value)

    @field_validator("patterns")
    @classmethod
    def pattern_groups(cls, value):
        """Validate role groups and placeholders using the existing text preparation.

        args:
            cls: Target file settings class.
            value: Ordered role-to-pattern mapping.

        returns:
            The original mapping without normalizing source templates.
        """
        from .target_matching import prepare_text

        if set(value) != set(PATTERN_CLASSES):
            raise ValueError(f"targets.yaml patterns requires {list(PATTERN_CLASSES)} lists")
        for label, phrases in value.items():
            if not phrases:
                raise ValueError(f"Target patterns for {label} must be nonempty strings")
            for phrase in phrases:
                prepare_text(phrase)
        return value
