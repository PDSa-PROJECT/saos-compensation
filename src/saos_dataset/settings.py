"""Strict domain validation and layered runtime settings."""

import math
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def finite_number(value):
    """Accept only finite Python integers/floats without changing their type.

    args:
        value: Parsed YAML value or explicit override.

    returns:
        The original finite numeric value.
    """
    if type(value) not in (int, float) or (
        type(value) is float and not math.isfinite(value)
    ):
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


class RuntimeSettings(BaseSettings):
    """Machine settings and optional model overrides from the root .env/environment."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8", extra="ignore", cli_parse_args=False,
    )

    acquisition_max_gib: Annotated[int | float, AfterValidator(finite_number)] = Field(0.5, ge=0)
    acquisition_debug: bool = True
    acquisition_download_path: NonblankString = "tmp/raw"
    acquisition_timeout: Annotated[int | float, AfterValidator(finite_number)] = Field(20, gt=0)
    processing_input_path: NonblankString = "tmp/raw"
    processing_output_path: NonblankString = "tmp/processed"
    processing_max_gib: Annotated[int | float, AfterValidator(finite_number)] = Field(0.5, ge=0)
    processing_debug: bool = True
    processing_timeout: Annotated[int | float, AfterValidator(finite_number)] = Field(20, gt=0)
    embedding_device: Device = "mps"
    embedding_batch_size: int = Field(64, gt=0)
    embedding_model: NonblankString | None = None
    embedding_revision: NonblankString | None = None
    basal_device: Device = "mps"
    basal_model: NonblankString | None = None

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings,
        file_secret_settings,
    ):
        """Give explicit CLI values priority over process environment and dotenv.

        args:
            cls: Runtime settings class.
            settings_cls: Settings class supplied by Pydantic.
            init_settings: Explicit runtime CLI values provided by the loader.
            env_settings: Process environment values.
            dotenv_settings: Repository-root dotenv values.
            file_secret_settings: Unused secrets-directory source.

        returns:
            CLI, process environment and dotenv sources in priority order.
        """
        return init_settings, env_settings, dotenv_settings

    def values_for(self, module, *, explicit_only=False):
        """Select a module's runtime values without exposing other modules' settings.

        args:
            self: Loaded runtime settings.
            module: Acquisition, embedding or basal module prefix.
            explicit_only: Exclude built-in defaults when applying source overrides.

        returns:
            Unprefixed field values, excluding unset optional model overrides.
        """
        prefix = module + "_"
        return {
            name.removeprefix(prefix): value
            for name, value in self.model_dump(
                exclude_none=True, exclude_unset=explicit_only,
            ).items()
            if name.startswith(prefix)
        }

    def merge(self, module, values):
        """Place explicit runtime sources above YAML and built-in defaults below it.

        args:
            self: Loaded runtime settings.
            module: Acquisition, embedding or basal module prefix.
            values: Parsed YAML mapping, including legacy runtime fields if present.

        returns:
            Effective mapping ready for strict domain-schema validation.
        """
        if not isinstance(values, dict):
            raise ValueError(f"{module} settings must be a mapping")
        return {
            **self.values_for(module), **values,
            **self.values_for(module, explicit_only=True),
        }
