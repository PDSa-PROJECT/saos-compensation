"""HTTP sessions, SAOS response parsing and external locality downloads."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from ..storage.files import write_bytes, write_json

BASE_URL = "https://www.saos.org.pl/api"
LOCALITIES_URL = "https://opendata.geoportal.gov.pl/bdot10k/schemat2021/GPKG/OT_ADMS_P.gpkg"


def open_session():
    """Create an HTTP session shared across dump pages and court metadata.

    args:
        None.

    returns:
        A requests session to be closed by its caller's context manager.
    """
    return requests.Session()


def fetch_localities(timeout=30):
    """Download the official locality snapshot with one timed HTTP attempt.

    args:
        timeout: Connection/read timeout in seconds.

    returns:
        Original GeoPackage bytes.
    """
    with requests.get(LOCALITIES_URL, timeout=timeout) as response:
        response.raise_for_status()
        return response.content


def fetch_json(url, directory=None, session=None, timeout=30):
    """
    Fetch one SAOS response and optionally preserve its original bytes.

    args:
        url: Resource URL.
        directory: Input or output directory for this operation.
        session: Reusable HTTP session, when supplied.
        timeout: Connection/read timeout in seconds.

    returns:
        Decoded JSON response object.
    """
    if not url.startswith(BASE_URL + "/"):
        raise ValueError(f"Expected a SAOS API URL: {url}")
    client = session or requests
    with client.get(
        url, headers={"Accept": "application/json"}, timeout=timeout
    ) as response:
        response.raise_for_status()
        raw = response.content
        content_type = response.headers.get("Content-Type", "")
        if response.status_code != 200 or "json" not in content_type:
            raise ValueError(f"Unexpected JSON response: {url}")
    if directory is not None:
        key = hashlib.sha256(url.encode()).hexdigest()
        path = Path(directory) / f"{key}.json"
        write_bytes(path, raw)
        write_json(
            path.with_suffix(".meta.json"),
            {
                "url": url,
                "acquired_at": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
        )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {url}")
    return payload


def search_parameters(params):
    """Translate saved inclusive date bounds to SAOS search parameters.

    args:
        params: Checkpoint query using stable internal date keys.

    returns:
        Query accepted by the search endpoint.
    """
    names = {"judgmentStartDate": "judgmentDateFrom", "judgmentEndDate": "judgmentDateTo"}
    return {names.get(key, key): value for key, value in params.items()}


def validate_search_query(payload, params):
    """Require the search response to acknowledge every requested filter.

    args:
        payload: Live or persisted search response.
        params: Internal or API query parameters.

    returns:
        None.
    """
    template = payload.get("queryTemplate")
    if not isinstance(template, dict):
        raise ValueError("Search response is missing queryTemplate")
    for key, value in search_parameters(params).items():
        applied = template.get(key)
        applied = applied.get("value") if isinstance(applied, dict) else applied
        expected = [value] if key == "judgmentTypes" else value
        if applied != expected:
            raise ValueError(f"API did not apply {key}")


def search_judgments(params, directory=None, session=None, timeout=30):
    """
    Search broadly, validate pagination and fetch every complete judgment.

    args:
        params: Effective SAOS query parameters.
        directory: Input or output directory for this operation.
        session: Reusable HTTP session, when supplied.
        timeout: Connection/read timeout in seconds.

    returns:
        Search envelope with complete items and original searchItems snippets.
    """
    params = search_parameters(params)
    url = (
        requests.Request("GET", BASE_URL + "/search/judgments", params=params)
        .prepare()
        .url
    )
    result = fetch_json(url, directory, session, timeout)
    if not isinstance(result.get("items"), list) or not isinstance(
        result.get("links"), list
    ):
        raise ValueError("Search response is missing items or pagination links")
    validate_search_query(result, params)
    ids = [
        item.get("id") if isinstance(item, dict) else None for item in result["items"]
    ]
    if any(type(value) is not int or value <= 0 for value in ids):
        raise ValueError("Search returned an invalid judgment ID")
    if len(ids) != len(set(ids)) or len(ids) > params["pageSize"]:
        raise ValueError("Search returned duplicate IDs or an oversized page")
    relations = set()
    for link in result["links"]:
        if (
            not isinstance(link, dict)
            or link.get("rel")
            not in {"self", "next", "prev", "previous", "first", "last"}
            or not isinstance(link.get("href"), str)
        ):
            raise ValueError("Invalid pagination link")
        if link["rel"] in relations:
            raise ValueError("Duplicate pagination relation")
        relations.add(link["rel"])
    if "self" not in relations or ("next" in relations and not ids):
        raise ValueError("Invalid search pagination")
    items = []
    for item in result["items"]:
        identifier = item["id"]
        detail = fetch_json(f"{BASE_URL}/judgments/{identifier}", directory, session, timeout)
        data = detail.get("data")
        if (
            not isinstance(data, dict)
            or type(data.get("id")) is not int
            or data["id"] != identifier
            or not isinstance(data.get("textContent"), str)
            or not data["textContent"].strip()
        ):
            raise ValueError(f"Invalid full judgment response: {identifier}")
        items.append(data)
    return {**result, "searchItems": result["items"], "items": items}



def search_courts(page, session=None, timeout=30):
    """Fetch one raw court dump page and validate its transport envelope.

    args:
        page: Zero-based court dump page.
        session: Shared HTTP session.
        timeout: Explicit HTTP timeout in seconds.

    returns:
        Original court response, retaining every API field.
    """
    payload = fetch_json(f"{BASE_URL}/dump/commonCourts?pageSize=100&pageNumber={page}", session=session, timeout=timeout)
    if not isinstance(payload.get("items"), list) or not isinstance(payload.get("links"), list):
        raise ValueError("Invalid common-court dump")
    ids = [row.get("id") if isinstance(row, dict) else None for row in payload["items"]]
    if any(type(value) is not int or value <= 0 for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Invalid or duplicate court IDs")
    relations = set()
    for link in payload["links"]:
        if not isinstance(link, dict) or link.get("rel") not in {"self", "next", "prev", "previous", "first", "last"} or not isinstance(link.get("href"), str):
            raise ValueError("Invalid court pagination link")
        if link["rel"] in relations:
            raise ValueError("Duplicate court pagination relation")
        relations.add(link["rel"])
    if len(ids) > 100 or "self" not in relations or (not ids and "next" in relations):
        raise ValueError("Invalid common-court pagination")
    return payload
