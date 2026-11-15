"""Acquisition configuration and inclusive date bounds."""

from calendar import monthrange
from datetime import date
from pathlib import Path

from pydantic import Field, field_validator

from ..settings import FiniteNumber, NonblankString, Settings


class AcquisitionSettings(Settings):
    """Acquisition values after explicit CLI overrides have been applied."""

    max_age_years: int = Field(gt=0)
    max_pages: int = Field(ge=0)
    max_gib: FiniteNumber = Field(ge=0)
    debug: bool
    download_path: NonblankString
    timeout: FiniteNumber = Field(gt=0)

    @field_validator("download_path")
    @classmethod
    def relative_output_path(cls, value):
        """Preserve repository-relative output paths without normalizing their text.

        args:
            cls: Acquisition settings class.
            value: Nonblank output path.

        returns:
            The unchanged safe relative path.
        """
        if Path(value).is_absolute() or ".." in Path(value).parts:
            raise ValueError("download_path must be relative to the project root")
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
    settings = AcquisitionSettings.from_mapping(config)
    years = settings.max_age_years
    end = today or date.today()
    if years >= end.year:
        raise ValueError("max_age_years exceeds the supported date range")
    start = end.replace(
        year=end.year - years,
        day=min(end.day, monthrange(end.year - years, end.month)[1]),
    )
    params = {
        "pageSize": 100,
        "pageNumber": 0,
        "judgmentStartDate": start.isoformat(),
        "judgmentEndDate": end.isoformat(),
    }
    return start, end, params
