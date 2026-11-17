import hashlib
import json

import pytest
import requests

from dataset.acquisition.settings import search_settings
from dataset.clients import api

CONFIG = {
    "max_age_years": 10,
    "max_pages": 0,
    "max_gib": 0,
    "debug": False,
    "download_path": "tmp/",
    "timeout": 30,
}


def search_response(params, identifiers, more=False):
    """
    Provide the search response behavior used by this operation.

    args:
        params: Effective SAOS query parameters.
        identifiers: Input for this operation.
        more: Input for this operation.

    returns:
        Result of this operation.
    """
    return {
        "items": [{"id": identifier} for identifier in identifiers],
        "info": None,
        "queryTemplate": {key: {"value": [value] if key == "judgmentTypes" else value} for key, value in params.items()},
        "links": [{"rel": "self", "href": api.BASE_URL + "/dump/judgments"}]
        + (
            [
                {
                    "rel": "next",
                    "href": api.BASE_URL + "/dump/judgments?pageNumber=1",
                }
            ]
            if more
            else []
        ),
    }


@pytest.mark.parametrize("defect", ["query", "duplicate", "links", "id", "empty_next"])
def test_invalid_dump_response_stops_download(monkeypatch, tmp_path, defect):
    """
    Verify invalid dump response stops download.

    args:
        monkeypatch: Scoped replacements for the test.
        tmp_path: Isolated temporary directory.
        defect: Malformed field under examination.

    returns:
        None.
    """
    _, _, params = search_settings(CONFIG)
    payload = search_response(api.search_parameters(params), [1, 2], True)
    if defect == "query":
        payload["queryTemplate"]["judgmentDateFrom"]["value"] = "2000-01-01"
    elif defect == "duplicate":
        payload["items"][1] = payload["items"][0]
    elif defect == "id":
        payload["items"][0]["id"] = True
    elif defect == "empty_next":
        payload["items"] = []
    else:
        payload["links"] = []
    monkeypatch.setattr(api, "fetch_json", lambda *args: payload)
    with pytest.raises(ValueError):
        api.search_judgments(params, tmp_path)


@pytest.mark.parametrize("debug", [False, True])
def test_http_reads_fresh_data_and_saves_raw_only_in_debug(
    monkeypatch,
    tmp_path,
    debug,
):
    """
    Verify http reads fresh data and saves raw only in debug.

    args:
        monkeypatch: Scoped replacements for the test.
        tmp_path: Isolated temporary directory.
        debug: Whether to save diagnostic artifacts.

    returns:
        None.
    """
    calls = []
    raw = b'{"data": {"id": 42}, "untouched": [1, null]}'

    class Response:
        content = raw
        headers = {"Content-Type": "application/json"}
        status_code = 200

        def raise_for_status(self):
            """
            Provide the raise for status behavior used by this operation.

            args:
                None

            returns:
                Result of this operation.
            """
            pass

        def __enter__(self):
            """
            Provide the   enter   behavior used by this operation.

            args:
                None

            returns:
                Result of this operation.
            """
            return self

        def __exit__(self, *args):
            """
            Provide the   exit   behavior used by this operation.

            args:
                args: Input for this operation.

            returns:
                Result of this operation.
            """
            pass

    def get(url, **kwargs):
        """
        Provide the get behavior used by this operation.

        args:
            url: Resource URL.
            kwargs: Input for this operation.

        returns:
            Result of this operation.
        """
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr(requests, "get", get)
    url = api.BASE_URL + "/judgments/42"
    directory = tmp_path if debug else None
    assert api.fetch_json(url, directory, timeout=12) == json.loads(raw)
    assert api.fetch_json(url, directory, timeout=12) == json.loads(raw)
    assert len(calls) == 2 and calls[0]["timeout"] == 12
    assert bool(list(tmp_path.iterdir())) == debug
    if debug:
        path = tmp_path / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        assert path.read_bytes() == raw
        assert (
            json.loads(path.with_suffix(".meta.json").read_text())["sha256"]
            == hashlib.sha256(raw).hexdigest()
        )


def test_http_timeout_is_not_retried(monkeypatch):
    """
    Verify http timeout is not retried.

    args:
        monkeypatch: Scoped replacements for the test.

    returns:
        None.
    """
    calls = []

    def get(*args, **kwargs):
        """
        Provide the get behavior used by this operation.

        args:
            args: Input for this operation.
            kwargs: Input for this operation.

        returns:
            Result of this operation.
        """
        calls.append(kwargs)
        raise requests.Timeout("offline")

    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(requests.Timeout):
        api.fetch_json(api.BASE_URL + "/dump/judgments", timeout=4)
    assert len(calls) == 1


@pytest.mark.parametrize("defect", [None, "ids", "duplicate", "links", "empty_next"])
def test_court_dump_validates_transport_without_processing(monkeypatch, defect):
    """Retain court payloads while rejecting unsafe pagination and identifiers.

    args:
        monkeypatch: Scoped HTTP boundary replacement.
        defect: Malformed transport field, or None for a valid response.

    returns:
        None.
    """
    payload = {"items": [{"id": 1, "unknown": [True]}], "links": [{"rel": "self", "href": "page"}]}
    if defect == "ids":
        payload["items"][0]["id"] = True
    elif defect == "duplicate":
        payload["items"] *= 2
    elif defect == "links":
        payload["links"] *= 2
    elif defect == "empty_next":
        payload["items"] = []
        payload["links"].append({"rel": "next", "href": "next"})
    monkeypatch.setattr(api, "fetch_json", lambda *args, **kwargs: payload)
    if defect:
        with pytest.raises(ValueError):
            api.search_courts(0)
    else:
        assert api.search_courts(0) is payload


@pytest.mark.parametrize("defect", [None, "id", "text", "timeout", "query"])
def test_search_fetches_complete_judgments(monkeypatch, defect):
    """Fetch full sources using one session and reject partial or mismatched pages.

    args:
        monkeypatch: HTTP boundary replacement.
        defect: Failure to inject into the search or full judgment response.

    returns:
        None.
    """
    from urllib.parse import parse_qs, urlparse

    params = search_settings(CONFIG)[2]
    query = api.search_parameters(params)
    payload = search_response(query, [42])
    payload["queryTemplate"]["all"] = params["all"]
    if defect == "query":
        payload["queryTemplate"]["judgmentTypes"]["value"] = ["DECISION"]
    payload["items"][0]["textContent"] = "snippet"
    full = {"id": 42, "textContent": "<p>Complete source.</p>", "extra": [None, 7]}
    if defect == "id":
        full["id"] = 43
    if defect == "text":
        full["textContent"] = None
    calls = []
    session = object()

    def fetch(url, directory, client, timeout):
        """Return search snippets or full data while recording request controls.

        args:
            url: Requested SAOS endpoint.
            directory: Optional diagnostics destination.
            client: Shared session.
            timeout: Explicit HTTP timeout.

        returns:
            Search or detail JSON payload.
        """
        calls.append((url, client, timeout))
        if "/search/judgments" in url:
            assert parse_qs(urlparse(url).query)["all"] == ["zadośćuczynienie"]
            assert "judgmentDateFrom" in parse_qs(urlparse(url).query)
            return payload
        if defect == "timeout":
            raise requests.Timeout("detail unavailable")
        assert url.endswith("/judgments/42")
        return {"data": full}

    monkeypatch.setattr(api, "fetch_json", fetch)
    if defect:
        with pytest.raises(requests.Timeout if defect == "timeout" else ValueError):
            api.search_judgments(params, session=session, timeout=12)
    else:
        result = api.search_judgments(params, session=session, timeout=12)
        assert result["items"] == [full]
        assert result["searchItems"] == payload["items"]
    assert all(client is session and timeout == 12 for _, client, timeout in calls)
    assert len(calls) == (1 if defect == "query" else 2)
