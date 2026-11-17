"""Select and normalize model inputs from local, unmodified SAOS dump pages."""

import json
import re
from datetime import date
from pathlib import Path

from ..clients.api import BASE_URL
from ..extraction.source.text import MONEY, extract_text
from ..storage.checkpoints import save_checkpoint
from ..storage.files import remove_tree
from ..storage.raw import page_path, read_dataset, read_page
from ..storage.records import record_complete
from .validation import validate_judgment

ROOT = Path(__file__).resolve().parents[3]


def read_divisions(pages):
    """Join court and division metadata from saved court API responses.

    args:
        pages: Iterable of unmodified common-court dump responses.

    returns:
        Validated division records indexed by stable division ID.
    """
    divisions = {}
    for payload in pages:
        if not isinstance(payload.get("items"), list) or not isinstance(
            payload.get("links"), list
        ):
            raise ValueError("Invalid common-court dump")
        for court in payload["items"]:
            if (
                not isinstance(court, dict)
                or type(court.get("id")) is not int
                or court["id"] <= 0
                or not isinstance(court.get("name"), str)
                or not court["name"].strip()
                or not isinstance(court.get("divisions"), list)
                or court.get("type") not in {"DISTRICT", "REGIONAL", "APPEAL"}
            ):
                raise ValueError("Invalid court in dump")
            for division in court["divisions"]:
                if not isinstance(division, dict):
                    raise ValueError("Invalid division in court dump")
                identifier = division.get("id")
                if (
                    type(identifier) is not int
                    or identifier <= 0
                    or not isinstance(division.get("name"), str)
                    or identifier in divisions
                ):
                    raise ValueError("Invalid or duplicate division in dump")
                divisions[identifier] = {
                    **division,
                    "court": {key: court[key] for key in ("id", "name", "type")},
                }
    return divisions


def records_from_raw(settings, checkpoint, run_id):
    """Yield selected local cases and advance only after durable extraction or rejection.

    args:
        settings: Processing input/output locations and operational controls.
        checkpoint: Independent processing cursor and pinned raw request.
        run_id: Identifier included in console summaries.

    returns:
        Iterator of validated, enriched judgments ready for model extraction.
    """
    directory = ROOT / settings["input_path"]
    output = ROOT / settings["output_path"]
    raw, signature = read_dataset(directory)
    if signature != checkpoint["source_signature"]:
        raise ValueError("Raw input snapshot changed before processing")
    divisions = read_divisions(read_page(page_path(directory, "common_courts", number)) for number in range(raw["court_page"]))
    start = date.fromisoformat(checkpoint["request"]["judgmentStartDate"])
    end = date.fromisoformat(checkpoint["request"]["judgmentEndDate"])
    seen = set()
    summary = {"run_id": run_id, "selected": 0, "filtered": 0, "duplicates": 0, "rejected": [], "complete": False}
    try:
        for number in range(raw["page"]):
            payload = read_page(page_path(directory, "judgments", number))
            ids = [item["id"] for item in payload["items"]]
            if number < checkpoint["page"]:
                seen.update(ids)
                continue
            if checkpoint["page_ids"] is not None and checkpoint["page_ids"] != ids:
                raise ValueError("Raw page contents changed since processing checkpoint")
            checkpoint["page_ids"] = ids
            save_checkpoint(output, checkpoint)
            first = checkpoint["next_item"]
            for index, item in enumerate(payload["items"]):
                identifier = item["id"]
                if index < first:
                    seen.add(identifier)
                    continue
                checkpoint["next_item"] = index
                if identifier in seen:
                    summary["duplicates"] += 1
                    continue
                seen.add(identifier)
                path = output / str(identifier) / "record.json"
                if record_complete(path, identifier, checkpoint["dataset_id"]):
                    remove_tree(path.parent / "pending")
                    continue
                if item.get("courtType") != "COMMON" or item.get("judgmentType") != "SENTENCE":
                    summary["filtered"] += 1
                    continue
                html = item.get("textContent")
                text = extract_text(html) if isinstance(html, str) else ""
                if not text:
                    summary["rejected"].append({"id": identifier, "reason": "Missing judgment text"})
                    continue
                if not re.search(r"zadośćuczyn", text, re.I) or not MONEY.search(text):
                    summary["filtered"] += 1
                    continue
                division = item.get("division")
                division_id = division.get("id") if isinstance(division, dict) else None
                if type(division_id) is not int or division_id <= 0:
                    summary["rejected"].append({"id": identifier, "reason": "Invalid division ID"})
                    continue
                try:
                    data, text = validate_judgment({"data": {**item, "division": divisions.get(division_id, {})}}, identifier, start, end)
                except ValueError as error:
                    summary["rejected"].append({"id": identifier, "reason": str(error)})
                    continue
                record = {"id": identifier, "judgmentDate": data["judgmentDate"], "courtCases": data["courtCases"],
                          "division": data["division"], "text": text, "source_payload": item,
                          "source_url": f"{BASE_URL}/judgments/{identifier}"}
                save_checkpoint(output, checkpoint)
                summary["selected"] += 1
                yield record
                if not record.get("rejected") and not record_complete(path, identifier, checkpoint["dataset_id"]):
                    raise RuntimeError(f"Cannot advance checkpoint without a completed record: {identifier}")
                checkpoint["next_item"] = index + 1
                save_checkpoint(output, checkpoint)
            checkpoint.update(page=number + 1, next_item=0, page_ids=None)
            save_checkpoint(output, checkpoint)
        checkpoint["complete"] = True
        save_checkpoint(output, checkpoint)
        summary["complete"] = True
    except Exception as error:
        summary["error"] = str(error)
        raise
    finally:
        print(json.dumps(summary, ensure_ascii=False), flush=True)
