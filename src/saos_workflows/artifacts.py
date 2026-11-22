"""Plain Parquet publication and lazy references through ZenML artifact-store IO.

The small reference manifest holds provenance once per artifact. Loading it never
opens cases.parquet. Publication writes that manifest last; incomplete workspaces
must not be treated as completed artifacts. ZenML owns artifact versioning.
"""

import json
import shutil
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import pyarrow as pa
import pyarrow.parquet as pq
from zenml.artifact_stores.base_artifact_store import BaseArtifactStore
from zenml.enums import ArtifactType
from zenml.io import fileio
from zenml.materializers.base_materializer import BaseMaterializer

from .contracts import ArtifactMetadata, SCHEMA_VERSION, case_schema, validate_row

PARQUET_NAME = "cases.parquet"
REFERENCE_NAME = "reference.json"
COPY_BUFFER_BYTES = 1024 * 1024


def _child(uri, name):
    """Join an artifact URI without damaging cloud scheme separators.

    args:
        uri: Artifact directory URI.
        name: Fixed artifact filename.
    returns:
        Local or remote child URI.
    """
    return f"{uri.rstrip('/')}/{name}"


@dataclass(frozen=True)
class ParquetArtifact:
    """Reference to a completed table, not a loaded Arrow/Polars DataFrame."""

    uri: str
    row_count: int
    metadata: ArtifactMetadata
    artifact_store: BaseArtifactStore | None = field(default=None, repr=False, compare=False)

    @property
    def parquet_uri(self):
        """Resolve the plain object address available for lazy scans.

        args:
            self: Published artifact reference.
        returns:
            URI of cases.parquet, without downloading or opening it.
        """
        return _child(self.uri, PARQUET_NAME)

    @property
    def schema(self):
        """Resolve the declared schema without reading any table data.

        args:
            self: Published artifact reference.
        returns:
            Frozen Arrow schema for this artifact's configured text fields.
        """
        return case_schema(self.metadata.text_fields)

    def scan(self, *, storage_options=None):
        """Create a lazy Polars scan; credentials are configured independently.

        args:
            self: Published reference with a plain local/S3 Parquet URI.
            storage_options: Explicit Polars cloud options, not ZenML credentials.
        returns:
            LazyFrame; no collect, table read or artifact download is performed here.
        """
        import polars as pl

        return pl.scan_parquet(self.parquet_uri, storage_options=storage_options)


def _save_reference(artifact, io):
    """Commit the small manifest after the plain Parquet object is durable.

    args:
        artifact: Completed table reference.
        io: ZenML artifact store or its native fileio dispatcher.
    returns:
        None.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "row_count": artifact.row_count,
        "metadata": artifact.metadata.model_dump(mode="json"),
    }
    with io.open(_child(artifact.uri, REFERENCE_NAME), "w") as stream:
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False)


def load_artifact(uri, *, artifact_store=None):
    """Read only the reference manifest, never the Parquet object or full table.

    args:
        uri: Explicit artifact-version directory URI, never an implicit latest alias.
        artifact_store: Configured native ZenML store; fileio is used when omitted.
    returns:
        Lazy ParquetArtifact reference with declared schema and provenance.
    """
    io = artifact_store if artifact_store is not None else fileio
    with io.open(_child(uri, REFERENCE_NAME), "r") as stream:
        payload = json.load(stream)
    if set(payload) != {"schema_version", "row_count", "metadata"}:
        raise ValueError("Invalid Parquet reference manifest")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported judgment artifact schema version")
    count = payload["row_count"]
    if type(count) is not int or count < 0:
        raise ValueError("Invalid artifact row count")
    return ParquetArtifact(
        uri=uri, row_count=count, metadata=ArtifactMetadata.model_validate(payload["metadata"]),
        artifact_store=artifact_store,
    )


def write_cases(rows: Iterable[Mapping[str, Any]], uri: str, metadata: ArtifactMetadata,
                *, artifact_store=None, batch_size=1024):
    """Write validated rows in bounded batches, preserving rejected/skipped cases.

    args:
        rows: One complete row per unique stable SAOS ID; duplicate IDs are errors.
        uri: New workspace/artifact directory; completed outputs are never overwritten.
        metadata: Artifact-level queries, bounds, caps, hashes and identities.
        artifact_store: Native ZenML store or fileio dispatcher when omitted.
        batch_size: Maximum rows per Arrow batch; only IDs are retained across batches.
    returns:
        Completed ParquetArtifact reference. Failures leave no completion manifest.
    """
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("Parquet batch_size must be a positive integer")
    io = artifact_store if artifact_store is not None else fileio
    if any(io.exists(_child(uri, name)) for name in (PARQUET_NAME, REFERENCE_NAME)):
        raise FileExistsError("Refusing to overwrite an existing judgment artifact")
    io.makedirs(uri)
    schema = case_schema(metadata.text_fields)
    seen, batch, count = set(), [], 0
    with io.open(_child(uri, PARQUET_NAME), "wb") as stream:
        with pq.ParquetWriter(stream, schema, compression="zstd") as writer:
            for row in rows:
                prepared = validate_row(row, metadata)
                identifier = prepared["saos_id"]
                if identifier in seen:
                    raise ValueError(f"Duplicate SAOS ID: {identifier}")
                seen.add(identifier)
                batch.append(prepared)
                count += 1
                if len(batch) == batch_size:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                    batch.clear()
            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
    artifact = ParquetArtifact(uri, count, metadata, artifact_store)
    _save_reference(artifact, io)
    return artifact


class ParquetArtifactMaterializer(BaseMaterializer):
    """ZenML 0.99 reference materializer, without eager Polars table loading."""

    ASSOCIATED_TYPES = (ParquetArtifact,)
    ASSOCIATED_ARTIFACT_TYPE = ArtifactType.DATA

    def save(self, data):
        """Stream the completed plain object into the configured artifact store.

        args:
            self: Materializer bound to a new ZenML artifact-version URI.
            data: Completed source ParquetArtifact, local or remote.
        returns:
            None; the destination manifest is published only after successful copy.
        """
        self.validate_save_type_compatibility(type(data))
        destination = self.artifact_store
        source = data.artifact_store if data.artifact_store is not None else fileio
        # A reference must originate from a completed writer, not an arbitrary path.
        completed = load_artifact(data.uri, artifact_store=data.artifact_store)
        if completed.row_count != data.row_count or completed.metadata != data.metadata:
            raise ValueError("Parquet reference differs from its completion manifest")
        if any(destination.exists(_child(self.uri, name)) for name in (PARQUET_NAME, REFERENCE_NAME)):
            raise FileExistsError("Refusing to overwrite an existing judgment artifact")
        destination.makedirs(self.uri)
        with source.open(data.parquet_uri, "rb") as reader:
            with destination.open(_child(self.uri, PARQUET_NAME), "wb") as writer:
                shutil.copyfileobj(reader, writer, length=COPY_BUFFER_BYTES)
        _save_reference(ParquetArtifact(self.uri, data.row_count, data.metadata), destination)

    def load(self, data_type):
        """Return only a URI/schema reference using the configured store's IO.

        args:
            self: Materializer bound to the selected artifact version.
            data_type: Requested ParquetArtifact type.
        returns:
            Reference; never calls read_table, collect or a whole-artifact download.
        """
        self.validate_load_type_compatibility(data_type)
        return load_artifact(self.uri, artifact_store=self.artifact_store)
