"""Complete SAOS sources and reproducible local input snapshots."""

import hashlib
import json
from datetime import date
from pathlib import Path

from .files import write_json


def page_path(directory, group, number):
    """Locate one raw API response without modifying its payload.

    args:
        directory: Raw dataset root.
        group: judgments or common_courts.
        number: Zero-based source page.

    returns:
        Path of the raw response JSON.
    """
    return Path(directory) / group / f"{number:08d}.json"


def read_page(path):
    """Read a raw response and validate its page envelope and stable identifiers.

    args:
        path: Raw API response file.

    returns:
        Original parsed response with all fields retained.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list) or not isinstance(payload.get("links"), list):
        raise ValueError(f"Invalid raw dump page: {path}")
    ids = [row.get("id") if isinstance(row, dict) else None for row in payload["items"]]
    if any(type(value) is not int or value <= 0 for value in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"Invalid or duplicate raw identifiers: {path}")
    if any(not isinstance(link, dict) or not isinstance(link.get("rel"), str) or not isinstance(link.get("href"), str) for link in payload["links"]):
        raise ValueError(f"Invalid raw pagination links: {path}")
    if not payload["items"] and any(link["rel"] == "next" for link in payload["links"]):
        raise ValueError(f"Empty raw page before next link: {path}")
    return payload


def write_page(path, payload):
    """Persist a response atomically without overwriting a different source artifact.

    args:
        path: Destination raw page.
        payload: Original API response, including unrecognized fields.

    returns:
        None.
    """
    path = Path(path)
    if path.exists():
        if read_page(path) != payload:
            raise ValueError(f"Raw page already contains different data: {path}")
        return
    write_json(path, payload)


def read_dataset(directory):
    """Identify a committed raw snapshot and hash all of its source pages.

    args:
        directory: Raw dataset root with its download checkpoint.

    returns:
        Raw checkpoint and content signature for processing compatibility.
    """
    directory = Path(directory)
    checkpoint = json.loads((directory / "checkpoint.json").read_text(encoding="utf-8"))
    if not isinstance(checkpoint, dict) or checkpoint.get("kind") != "raw":
        raise ValueError("Processing requires a get-raw-data dataset")
    for name in ("page", "court_page"):
        if type(checkpoint.get(name)) is not int or checkpoint[name] < 0:
            raise ValueError(f"Invalid raw checkpoint {name}")
    if type(checkpoint.get("complete")) is not bool or type(checkpoint.get("courts_complete")) is not bool:
        raise ValueError("Invalid raw checkpoint completion flags")
    if not checkpoint["courts_complete"] or not checkpoint["court_page"] or not checkpoint["page"]:
        raise ValueError("Raw dataset has no committed judgment pages or incomplete court metadata")
    if not isinstance(checkpoint.get("dataset_id"), str) or not checkpoint["dataset_id"] or not isinstance(checkpoint.get("request"), dict):
        raise ValueError("Invalid raw dataset identity")
    try:
        request = checkpoint["request"]
        start = date.fromisoformat(request["judgmentStartDate"])
        end = date.fromisoformat(request["judgmentEndDate"])
        if start > end or request.get("pageSize") != 100 or type(request.get("pageNumber")) is not int or request["pageNumber"] != 0:
            raise ValueError("Invalid raw request bounds or pagination")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid raw checkpoint request") from error
    digest = hashlib.sha256(json.dumps({key: checkpoint[key] for key in ("dataset_id", "request", "page", "court_page")}, sort_keys=True).encode())
    for group, count in (("common_courts", checkpoint["court_page"]), ("judgments", checkpoint["page"])):
        for number in range(count):
            path = page_path(directory, group, number)
            digest.update(str(path.relative_to(directory)).encode())
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
    return checkpoint, digest.hexdigest()
