"""Track feature extraction from a target-enriched local Parquet file."""

from zenml import pipeline, step

from saos_workflows.operations.features import extract_features_to_parquet


@step(enable_cache=False)
def extract_features_step(input_path: str, output_path: str, config_dir: str | None = None) -> str:
    """Run predictor extraction and publish a distinct Parquet file.

    args:
        input_path: Existing target-enriched Parquet path.
        output_path: New local Parquet path, distinct from input.
        config_dir: Optional existing processing YAML directory.
    returns:
        Path of the completed feature-enriched file.
    """
    return extract_features_to_parquet(input_path, output_path, config_dir)


@pipeline
def extract_features(input_path: str, output_path: str, config_dir: str | None = None) -> str:
    """Track source-grounded feature extraction and admission.

    args:
        input_path: Explicit target artifact path.
        output_path: Explicit new output path.
        config_dir: Optional existing processing YAML directory.
    returns:
        Path of the published feature-enriched artifact.
    """
    return extract_features_step(input_path=input_path, output_path=output_path, config_dir=config_dir)
