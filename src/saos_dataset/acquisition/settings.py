"""Acquisition configuration and inclusive date bounds."""

from calendar import monthrange
from datetime import date
from pathlib import Path

from pydantic import Field, field_validator

from ..settings import FiniteNumber, NonblankString, Settings, RuntimeSettings
from ..configuration import ROOT, read_config, validate_path


class AcquisitionSettings(Settings):
    """Acquisition values after explicit CLI overrides have been applied."""

    search_query: NonblankString
    max_age_years: int = Field(gt=0)
    max_pages: int = Field(ge=0)
    max_gib: FiniteNumber = Field(ge=0)
    debug: bool
    download_path: NonblankString
    timeout: FiniteNumber = Field(gt=0)

    @field_validator("download_path")
    @classmethod
    def output_path(cls, value):
        """Validate filesystem output paths without restricting their location.

        args:
            cls: Acquisition settings class.
            value: Nonblank output path.

        returns:
            The unchanged filesystem path.
        """
        validate_path(value, "download_path")
        return value


def search_settings(config, today=None):
    """
    Validate acquisition settings and derive inclusive judgment-date bounds.

    args:
        config: Effective pipeline or acquisition settings.
        today: Date used to anchor the acquisition range.

    returns:
        Start date, end date and effective query parameters.
    """
    settings = AcquisitionSettings.from_mapping({"search_query": "zadośćuczynienie", **config})
    years = settings.max_age_years
    end = today or date.today()
    if years >= end.year:
        raise ValueError("max_age_years exceeds the supported date range")
    start = end.replace(
        year=end.year - years,
        day=min(end.day, monthrange(end.year - years, end.month)[1]),
    )
    params = {
        "all": settings.search_query,
        "courtType": "COMMON",
        "judgmentTypes": "SENTENCE",
        "sortingField": "DATABASE_ID",
        "sortingDirection": "ASC",
        "pageSize": 100,
        "pageNumber": 0,
        "judgmentStartDate": start.isoformat(),
        "judgmentEndDate": end.isoformat(),
    }
    return start, end, params


def load_config(directory=None, overrides=None):
    """Load only acquisition YAML and apply explicit download overrides.

    args:
        directory: Directory containing api.yaml or None for the repository default.
        overrides: Explicit CLI acquisition values.

    returns:
        Validated download settings without model configuration.
    """
    directory = Path(directory) if directory is not None else ROOT / "configs/dataset/acquisition"
    overrides = overrides or {}
    runtime = RuntimeSettings(**{
        "acquisition_" + key: value for key, value in overrides.items()
        if "acquisition_" + key in RuntimeSettings.model_fields
    })
    settings = runtime.merge("acquisition", read_config(directory / "api.yaml"))
    settings.update(overrides)
    search_settings(settings)
    return settings
