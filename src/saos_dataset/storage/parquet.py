"""Judgment row schema, validation and Parquet serialization."""

import json

import pyarrow as pa
import pyarrow.parquet as pq

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
    with open(path, "xb") as output:
        pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), output)


def read_rows(path):
    """Validate a Parquet schema and return judgment rows.

    args:
        path: Parquet path or readable seekable artifact-store stream.

    returns:
        List of judgment row dictionaries in source order.
    """
    table = pq.read_table(path)
    if not table.schema.equals(SCHEMA, check_metadata=False):
        raise ValueError("Input judgment artifact has an incompatible column layout")
    return table.to_pylist()
