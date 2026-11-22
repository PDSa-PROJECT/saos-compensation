"""Collect complete SAOS cases into the local judgment row layout."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import ConfigDict, Field, validate_call

from saos_dataset.clients import api
from saos_dataset.processing.source import read_divisions, select_judgment
from saos_dataset.settings import FiniteNumber, NonblankString

from .rows import write_rows


@validate_call(config=ConfigDict(strict=True, arbitrary_types_allowed=True))
def collect_to_parquet(
    start_date: NonblankString,
    end_date: NonblankString,
    phrases: Annotated[list[NonblankString], Field(min_length=1)],
    output_path: NonblankString | Path,
    selected_phrases: Annotated[list[NonblankString], Field(min_length=1)] | None = None,
    max_records: Annotated[int, Field(ge=0)] = 0,
    timeout: Annotated[FiniteNumber, Field(gt=0)] = 30.0,
    session: object | None = None,
):
    """Validate collection inputs and publish one complete local Parquet file.

    args:
        start_date: Inclusive judgment date in ISO format.
        end_date: Inclusive judgment date in ISO format.
        phrases: Configured SAOS search phrases in retrieval order.
        output_path: New local Parquet file destination.
        selected_phrases: Subset to search, or None to search all phrases.
        max_records: Maximum unique details to fetch; zero means unlimited.
        timeout: Positive per-request HTTP timeout in seconds.
        session: Optional caller-owned session for offline verification.

    returns:
        Path string for the complete local Parquet file.
    """
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start_date must not be after end_date")
    if selected_phrases is None:
        selected_phrases = phrases
    if (
        len(set(phrases)) != len(phrases)
        or len(set(selected_phrases)) != len(selected_phrases)
        or not set(selected_phrases) <= set(phrases)
    ):
        raise ValueError("selected_phrases must be a nonempty subset of phrases")
    if not str(output_path).strip():
        raise ValueError("output_path must be a nonblank local path")
    path = Path(output_path)
    if path.exists():
        raise FileExistsError(f"Parquet file already exists: {path}")

    if session is None:
        with api.open_session() as shared_session:
            rows = collect_rows(start, end, selected_phrases, max_records, timeout, shared_session)
    else:
        rows = collect_rows(start, end, selected_phrases, max_records, timeout, session)
    write_rows(path, rows)
    return str(path)


def collect_rows(start, end, phrases, max_records, timeout, session):
    """Fetch unique judgment details and retain selected and unselected cases.

    args:
        start: First included judgment date.
        end: Last included judgment date.
        phrases: Search phrases in retrieval order.
        max_records: Maximum unique details, or zero for unlimited.
        timeout: Per-request HTTP timeout.
        session: Shared HTTP session.

    returns:
        Judgment rows retaining complete SAOS detail responses.
    """
    court_pages = []
    page = 0
    while True:
        payload = api.search_courts(page, session=session, timeout=timeout)
        court_pages.append(payload)
        if not any(link["rel"] == "next" for link in payload["links"]):
            break
        page += 1
    divisions = read_divisions(court_pages)

    rows = []
    seen = set()
    for phrase in phrases:
        page = 0
        while True:
            params = {
                "all": phrase,
                "courtType": "COMMON",
                "judgmentTypes": "SENTENCE",
                "sortingField": "DATABASE_ID",
                "sortingDirection": "ASC",
                "pageSize": 100,
                "pageNumber": page,
                "judgmentStartDate": start.isoformat(),
                "judgmentEndDate": end.isoformat(),
            }
            result = api.search_judgments_page(params, session=session, timeout=timeout)
            for item in result["items"]:
                identifier = item["id"]
                if identifier in seen:
                    continue
                detail = api.fetch_judgment(identifier, session=session, timeout=timeout)
                selection = select_judgment(detail["data"], divisions, start, end)
                record = selection["record"]
                rows.append({
                    "saos_id": identifier,
                    "source_json": json.dumps(detail, ensure_ascii=False),
                    "selected_record_json": json.dumps(record, ensure_ascii=False) if record is not None else None,
                    "judgment_text": record["text"] if record is not None else None,
                    "selection_status": selection["status"],
                    "selection_reason": selection["reason"],
                    "target_json": None,
                    "features_json": None,
                    "target_total_pln": None,
                    "eligible": None,
                })
                seen.add(identifier)
                if max_records and len(seen) >= max_records:
                    return rows
            if not any(link["rel"] == "next" for link in result["links"]):
                break
            page += 1
    return rows
