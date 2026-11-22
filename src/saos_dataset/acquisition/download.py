"""Broad SAOS search and complete judgment acquisition without inference."""

import json
from datetime import datetime, timezone
from pathlib import Path

from saos_dataset.clients import api
from saos_dataset.storage.checkpoints import load_raw_checkpoint, save_checkpoint
from saos_dataset.storage.files import StorageLimitError, output_limit
from saos_dataset.storage.raw import page_path, read_page, write_page
from .settings import search_settings

ROOT = Path(__file__).resolve().parents[3]


def download(config):
    """Save raw court and judgment pages before advancing their independent cursors.

    args:
        config: Validated acquisition settings without model configuration.

    returns:
        None.
    """
    search_settings(config)
    directory = ROOT / config["download_path"]
    checkpoint = load_raw_checkpoint(config)
    summary = {"started_at": datetime.now(timezone.utc).isoformat(), "pages": 0, "judgments": 0, "complete": False}
    try:
        with output_limit(directory, config["max_gib"]):
            if checkpoint["complete"] or (config["max_pages"] and checkpoint["page"] >= config["max_pages"]):
                print("No pending raw pages within the configured page limit.", flush=True)
                return
            save_checkpoint(directory, checkpoint)
            with api.open_session() as session:
                while not checkpoint["courts_complete"]:
                    number = checkpoint["court_page"]
                    path = page_path(directory, "common_courts", number)
                    payload = read_page(path) if path.exists() else api.search_courts(number, session, config["timeout"])
                    write_page(path, payload)
                    checkpoint.update(court_page=number + 1, courts_complete=not api.has_next_page(payload))
                    save_checkpoint(directory, checkpoint)
                while not checkpoint["complete"] and (not config["max_pages"] or checkpoint["page"] < config["max_pages"]):
                    number = checkpoint["page"]
                    path = page_path(directory, "judgments", number)
                    params = {**checkpoint["request"], "pageNumber": number}
                    payload = read_page(path) if path.exists() else api.search_judgments(params, session=session, timeout=config["timeout"])
                    api.validate_search_query(payload, params)
                    write_page(path, payload)
                    checkpoint.update(page=number + 1, complete=not api.has_next_page(payload))
                    save_checkpoint(directory, checkpoint)
                    summary["pages"] += 1
                    summary["judgments"] += len(payload["items"])
                    if config["debug"]:
                        print(f"Saved raw page {number}: {len(payload['items'])} judgments", flush=True)
            summary["complete"] = checkpoint["complete"]
    except StorageLimitError as error:
        print(f"{error}. Increase max_gib and rerun get-raw-data to resume.", flush=True)
    except Exception as error:
        summary["error"] = str(error)
        raise
    finally:
        print(json.dumps(summary), flush=True)
