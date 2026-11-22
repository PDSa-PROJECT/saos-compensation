"""Track target extraction from a selected local Parquet file."""

from zenml import pipeline, step

from saos_workflows.operations.targets import find_targets_to_parquet


@step(enable_cache=False)
def find_targets_step(input_path: str, output_path: str, config_dir: str | None = None) -> str:
    """Run target extraction and publish a distinct Parquet file.

    args:
        input_path: Explicit existing local Parquet input.
        output_path: Explicit new local Parquet output.
        config_dir: Optional existing processing YAML directory.
    returns:
        Path of the completed output file.
    """
    return find_targets_to_parquet(input_path, output_path, config_dir)


@pipeline
def find_targets(input_path: str, output_path: str, config_dir: str | None = None) -> str:
    """Run target extraction independently on one selected local artifact.

    args:
        input_path: Explicit source Parquet path.
        output_path: Explicit new Parquet path.
        config_dir: Optional existing processing YAML directory.
    returns:
        Path of the published target-enriched artifact.
    """
    return find_targets_step(input_path=input_path, output_path=output_path, config_dir=config_dir)
