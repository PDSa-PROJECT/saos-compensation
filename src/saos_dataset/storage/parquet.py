"""Plain local Parquet storage independent of workflow orchestration."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .files import write_bytes


def write_parquet(path, table):
    """Persist a caller-supplied Arrow table without replacing an existing file.

    args:
        path: New local Parquet file path.
        table: Arrow table whose schema and values are retained as supplied.

    returns:
        None.
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Parquet file already exists: {path}")
    if not isinstance(table, pa.Table):
        raise TypeError("Parquet storage requires a PyArrow table")
    buffer = pa.BufferOutputStream()
    pq.write_table(table, buffer)
    write_bytes(path, buffer.getvalue().to_pybytes())


def read_parquet(path):
    """Read a plain local Parquet file without a ZenML dependency.

    args:
        path: Existing local Parquet file path.

    returns:
        Arrow table with the stored columns and schema.
    """
    return pq.read_table(Path(path))
