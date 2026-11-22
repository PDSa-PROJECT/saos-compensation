"""Track local SAOS judgment collection with ZenML."""

from zenml import pipeline, step

from saos_workflows.operations.collection import collect_to_parquet


@step(enable_cache=False)
def collect_cases_step(start_date: str, end_date: str, phrases: list[str], output_path: str,
                       selected_phrases: list[str] | None = None, max_records: int = 0,
                       timeout: float = 30.0) -> str:
    """Collect cases and return the explicit local Parquet path.

    args:
        start_date: Inclusive first judgment date.
        end_date: Inclusive last judgment date.
        phrases: Configured search phrases.
        output_path: New local Parquet file destination.
        selected_phrases: Subset to search, or None for all phrases.
        max_records: Unique detail cap, with zero meaning unlimited.
        timeout: Per-request HTTP timeout in seconds.

    returns:
        Path string for the local Parquet file (not a ZenML file artifact).
    """
    return collect_to_parquet(start_date, end_date, phrases, output_path,
                              selected_phrases, max_records, timeout)


@pipeline
def collect_cases(start_date: str, end_date: str, phrases: list[str], output_path: str,
                  selected_phrases: list[str] | None = None, max_records: int = 0,
                  timeout: float = 30.0) -> str:
    """Track a local collection run and its explicit Parquet output path.

    args:
        start_date: Inclusive first judgment date.
        end_date: Inclusive last judgment date.
        phrases: Configured search phrases.
        output_path: New local Parquet file destination.
        selected_phrases: Subset to search, or None for all phrases.
        max_records: Unique detail cap, with zero meaning unlimited.
        timeout: Per-request HTTP timeout in seconds.

    returns:
        Path string emitted by the collection step.
    """
    return collect_cases_step(start_date=start_date, end_date=end_date, phrases=phrases,
                              output_path=output_path, selected_phrases=selected_phrases,
                              max_records=max_records, timeout=timeout)
