"""Shared explicit-input settings policy and non-coercing value constraints."""

import math
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def finite_number(value):
    """Accept only finite Python integers/floats without changing their type.

    args:
        value: Parsed YAML value or explicit override.

    returns:
        The original finite numeric value.
    """
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Value must be a finite number")
    return value


def probability(value):
    """Require an inclusive unit interval without treating similarity as confidence.

    args:
        value: Validated finite numeric value.

    returns:
        The unchanged value between zero and one.
    """
    if not 0 <= value <= 1:
        raise ValueError("Value must be between 0 and 1")
    return value


def nonblank(value):
    """Reject blank text while preserving original whitespace and source wording.

    args:
        value: Strictly validated string.

    returns:
        The unchanged nonblank string.
    """
    if not value.strip():
        raise ValueError("Text must be nonempty")
    return value


FiniteNumber = Annotated[int | float, BeforeValidator(finite_number)]
Probability = Annotated[FiniteNumber, AfterValidator(probability)]
NonblankString = Annotated[str, AfterValidator(nonblank)]
Device = Literal["cpu", "mps", "cuda"]


class Settings(BaseSettings):
    """Validate explicit mappings only; file loading and precedence belong to callers."""

    model_config = SettingsConfigDict(
        strict=True, extra="forbid", env_file=None, cli_parse_args=False,
    )

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings,
        file_secret_settings,
    ):
        """Exclude ambient environment, dotenv, secrets and CLI settings sources.

        args:
            cls: Concrete settings class.
            settings_cls: Settings class supplied by Pydantic.
            init_settings: Explicit constructor values.
            env_settings: Unused environment source.
            dotenv_settings: Unused dotenv source.
            file_secret_settings: Unused secrets-directory source.

        returns:
            Only the explicit-input source.
        """
        return (init_settings,)

    @classmethod
    def from_mapping(cls, value) -> Self:
        """Reject missing/extra keys before BaseSettings can consume control arguments.

        args:
            cls: Concrete settings class with required fields.
            value: Mapping loaded from YAML or supplied by a Python caller.

        returns:
            Validated settings with no implicit defaults or additional sources.
        """
        if not isinstance(value, dict) or set(value) != set(cls.model_fields):
            raise ValueError(
                f"{cls.__name__} accepts only {', '.join(cls.model_fields)} "
                "and requires every field"
            )
        return cls.model_validate(value)
