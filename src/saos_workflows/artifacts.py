"""ZenML-managed plain Parquet files with reference-only loading."""

from dataclasses import dataclass

from zenml import get_step_context
from zenml.enums import ArtifactType
from zenml.materializers.base_materializer import BaseMaterializer
from zenml.io import fileio

from saos_dataset.storage.parquet import read_rows, write_rows


@dataclass(frozen=True)
class ParquetArtifact:
    """Reference to a plain Parquet object, without loading its rows."""

    uri: str


class ParquetMaterializer(BaseMaterializer):
    """Publish Parquet through the configured local or S3 artifact store."""

    ASSOCIATED_TYPES = (ParquetArtifact,)
    ASSOCIATED_ARTIFACT_TYPE = ArtifactType.DATA

    def save(self, data):
        """Copy a completed local staging file into the managed artifact store.

        args:
            data: Reference to the completed local Parquet file.
        returns:
            None.
        """
        destination = self.uri.rstrip("/") + "/data.parquet"
        fileio.copy(data.uri, destination, overwrite=False)

    def load(self, data_type):
        """Resolve the managed object without downloading or reading the table.

        args:
            data_type: Requested Parquet reference type.
        returns:
            Reference to the stored plain Parquet object.
        """
        uri = self.uri.rstrip("/") + "/data.parquet"
        if not self.artifact_store.exists(uri):
            raise FileNotFoundError(uri)
        return ParquetArtifact(uri)


def write_artifact(rows):
    """Stage validated rows until ZenML publishes the step output.

    args:
        rows: Judgment rows using the shared dataset schema.
    returns:
        Reference to a staging file cleaned up after step execution.
    """
    materializer = get_step_context().get_output_materializer()
    with materializer.get_temporary_directory(delete_at_exit=False) as directory:
        path = directory + "/data.parquet"
        write_rows(path, rows)
        return ParquetArtifact(path)


def read_artifact(artifact):
    """Read stage input through ZenML's configured artifact-store transport.

    args:
        artifact: Explicitly selected managed Parquet reference.
    returns:
        Validated stage rows in their original order.
    """
    materializer = get_step_context().get_output_materializer()
    with materializer.artifact_store.open(artifact.uri, "rb") as source:
        return read_rows(source)
