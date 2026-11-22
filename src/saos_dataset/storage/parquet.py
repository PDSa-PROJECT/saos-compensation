"""Plain local Parquet storage independent of workflow orchestration."""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .files import write_bytes

SCHEMA = pa.schema([
    ("saos_id", pa.int64()),
    ("source_json", pa.large_string()),
    ("selected_record_json", pa.large_string()),
    ("judgment_text", pa.large_string()),
    ("selection_status", pa.string()),
    ("selection_reason", pa.string()),
    ("target_json", pa.large_string()),
    ("features_json", pa.large_string()),
    ("target_total_pln", pa.decimal128(38, 2)),
    ("eligible", pa.bool_()),
])


def write_rows(path, rows):
    """Write complete source-backed rows to a new local Parquet file.

    args:
        path: New version's local Parquet path.
        rows: Stage rows using the shared column names.

    returns:
        None.
    """
    rows = list(rows)
    seen = set()
    for row in rows:
        identifier = row.get("saos_id")
        if type(identifier) is not int or identifier <= 0 or identifier >= 2**63 or identifier in seen:
            raise ValueError("Invalid or duplicate SAOS ID")
        seen.add(identifier)
        if set(row) != set(SCHEMA.names):
            raise ValueError("Judgment row columns do not match the pipeline layout")
        source = json.loads(row["source_json"])
        if (not isinstance(source, dict) or not isinstance(source.get("data"), dict)
                or type(source["data"].get("id")) is not int or source["data"]["id"] != identifier):
            raise ValueError("Judgment row does not match its complete source response")
    write_parquet(path, pa.Table.from_pylist(rows, schema=SCHEMA))


def read_rows(path):
    """Read one explicitly selected local Parquet version as stage rows.

    args:
        path: Existing local Parquet file to process.

    returns:
        List of judgment row dictionaries in source order.
    """
    table = read_parquet(path)
    if not table.schema.equals(SCHEMA, check_metadata=False):
        raise ValueError("Input judgment artifact has an incompatible column layout")
    return table.to_pylist()


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
