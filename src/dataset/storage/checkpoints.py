"""Independent raw-download and local-processing progress."""

import hashlib
import json
from datetime import date
from pathlib import Path
from uuid import uuid4

from ..acquisition.settings import search_settings
from .files import write_json
from .raw import read_dataset

ROOT = Path(__file__).resolve().parents[3]


def save_checkpoint(directory, checkpoint):
    """Atomically persist progress after its corresponding output is durable.

    args:
        directory: Stage-specific output directory.
        checkpoint: Raw download or processing state.

    returns:
        None.
    """
    write_json(Path(directory) / "checkpoint.json", checkpoint)


def read_checkpoint(directory, kind):
    """Read one stage's checkpoint without adopting existing unrelated artifacts.

    args:
        directory: Stage-specific output directory.
        kind: Expected raw or processing stage.

    returns:
        Saved state, or None for an empty new destination.
    """
    directory = Path(directory)
    path = directory / "checkpoint.json"
    if not path.exists():
        if directory.exists() and any(directory.iterdir()):
            raise ValueError("Output contains artifacts without a compatible checkpoint; use a different output directory")
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("kind") != kind:
        raise ValueError(f"Expected a {kind} checkpoint; use a different output directory")
    if not isinstance(state.get("dataset_id"), str) or not state["dataset_id"]:
        raise ValueError("Invalid checkpoint dataset ID")
    if type(state.get("page")) is not int or state["page"] < 0 or type(state.get("complete")) is not bool:
        raise ValueError("Invalid checkpoint progress")
    return state


def load_raw_checkpoint(config):
    """Resume download dates and page cursors without depending on extraction settings.

    args:
        config: Validated acquisition-only settings.

    returns:
        Saved raw state or a new raw dataset identity and date-bounded query.
    """
    _, _, request = search_settings(config)
    state = read_checkpoint(ROOT / config["download_path"], "raw")
    if state is None:
        return {"kind": "raw", "dataset_id": uuid4().hex, "request": request,
                "page": 0, "court_page": 0, "courts_complete": False, "complete": False}
    if set(state) != {"kind", "dataset_id", "request", "page", "court_page", "courts_complete", "complete"}:
        raise ValueError("Invalid raw checkpoint structure")
    if type(state["court_page"]) is not int or state["court_page"] < 0 or type(state["courts_complete"]) is not bool:
        raise ValueError("Invalid raw court progress")
    try:
        expected = search_settings(config, date.fromisoformat(state["request"]["judgmentEndDate"]))[2]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid raw checkpoint request") from error
    if state["request"] != expected:
        raise ValueError("Acquisition query or date settings changed; use a different download_path")
    return state


def load_checkpoint(config):
    """Bind processing progress to extraction settings and an immutable raw snapshot.

    args:
        config: Effective model and processing configuration.

    returns:
        Compatible processing state or a new independent processing checkpoint.
    """
    settings = config["processing"]
    raw, source_signature = read_dataset(ROOT / settings["input_path"])
    signature = hashlib.sha256(json.dumps(
        {key: value for key, value in config.items() if key != "processing"},
        ensure_ascii=False, sort_keys=True,
    ).encode()).hexdigest()
    state = read_checkpoint(ROOT / settings["output_path"], "processing")
    if state is None:
        return {"kind": "processing", "dataset_id": uuid4().hex, "signature": signature,
                "source_signature": source_signature, "request": raw["request"],
                "page": 0, "next_item": 0, "page_ids": None, "complete": False,
                "localities_sha256": None}
    if set(state) != {"kind", "dataset_id", "signature", "source_signature", "request", "page", "next_item", "page_ids", "complete", "localities_sha256"}:
        raise ValueError("Invalid processing checkpoint structure")
    if state["signature"] != signature:
        raise ValueError("Extraction settings changed; use a different output_path")
    if state["source_signature"] != source_signature or state["request"] != raw["request"]:
        raise ValueError("Raw input snapshot changed; use a different output_path")
    if type(state["next_item"]) is not int or state["next_item"] < 0 or state["page"] > raw["page"]:
        raise ValueError("Invalid processing checkpoint position")
    ids = state["page_ids"]
    if ids is not None and (not isinstance(ids, list) or any(type(value) is not int or value <= 0 for value in ids) or len(ids) != len(set(ids))):
        raise ValueError("Invalid processing page IDs")
    if (ids is None and state["next_item"] != 0) or (ids is not None and state["next_item"] > len(ids)):
        raise ValueError("Processing checkpoint position exceeds saved page")
    if state["complete"] and (state["page"] != raw["page"] or ids is not None or state["next_item"] != 0):
        raise ValueError("Completed checkpoint has unfinished input")
    if state["page"] == raw["page"] and ids is not None:
        raise ValueError("Processing checkpoint points beyond the raw snapshot")
    digest = state["localities_sha256"]
    if digest is not None and (not isinstance(digest, str) or len(digest) != 64):
        raise ValueError("Invalid checkpoint locality snapshot hash")
    return state
