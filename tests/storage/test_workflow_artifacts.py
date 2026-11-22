"""Managed Parquet publication and reference-only artifact loading."""

from types import SimpleNamespace
from pathlib import Path

import pytest

from saos_workflows.artifacts import ParquetArtifact, ParquetMaterializer
from saos_dataset.storage.parquet import read_rows, write_rows


def test_materializer_publishes_bytes_and_loads_only_reference(tmp_path):
    """Keep a durable managed copy and avoid table reads during resolution.

    args:
        tmp_path: Isolated staging and managed file locations.
    returns:
        None.
    """
    source = tmp_path / "staging.parquet"
    write_rows(source, [])
    original = source.read_bytes()
    destination = tmp_path / "artifact"
    destination.mkdir()
    store = SimpleNamespace(exists=lambda uri: Path(uri).exists(), open=open)
    materializer = ParquetMaterializer(str(destination), artifact_store=store)
    materializer.save(ParquetArtifact(str(source)))
    source.unlink()
    reference = materializer.load(ParquetArtifact)
    assert reference.uri == str(destination / "data.parquet")
    assert (destination / "data.parquet").read_bytes() == original
    assert read_rows(reference.uri) == []
    with pytest.raises(FileExistsError):
        materializer.save(reference)


def test_materializer_resolves_s3_uri_without_opening_data():
    """Use the configured store for URI existence without downloading a table.

    args:
        None.
    returns:
        None.
    """
    checked = []
    store = SimpleNamespace(exists=lambda uri: checked.append(uri) or True)
    materializer = ParquetMaterializer("s3://bucket/version", artifact_store=store)
    reference = materializer.load(ParquetArtifact)
    assert reference.uri == "s3://bucket/version/data.parquet"
    assert checked == [reference.uri]


def test_missing_managed_file_fails():
    """Surface a missing stored object instead of returning a dangling reference.

    args:
        None.
    returns:
        None.
    """
    store = SimpleNamespace(exists=lambda uri: False)
    with pytest.raises(FileNotFoundError):
        ParquetMaterializer("missing", artifact_store=store).load(ParquetArtifact)
