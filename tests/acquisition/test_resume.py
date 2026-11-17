"""Raw acquisition durability, separation and resume contracts."""

import json

import pytest
import requests

from dataset.acquisition import download
from dataset.acquisition.settings import load_config
from dataset.storage import checkpoints
from dataset.storage.raw import page_path, read_page


@pytest.fixture
def raw_download(monkeypatch, tmp_path):
    """Isolate raw output and replace only the external HTTP boundary.

    args:
        monkeypatch: Scoped overrides.
        tmp_path: Isolated output root.

    returns:
        Settings and captured page requests.
    """
    for module in (download, checkpoints):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    calls = []

    def courts(number, session, timeout):
        """Return an unprocessed court page.

        args:
            number: Requested page.
            session: Shared session.
            timeout: HTTP timeout.

        returns:
            Original court payload.
        """
        calls.append(("court", number, session, timeout))
        return {"items": [{"id": 1, "unknown": True}], "links": []}

    def judgments(params, session=None, timeout=None):
        """Return mixed raw items without domain selection.

        args:
            params: Requested query.
            session: Shared session.
            timeout: HTTP timeout.

        returns:
            Original judgment payload.
        """
        number = params["pageNumber"]
        calls.append(("judgment", number, session, timeout))
        return {
            "items": [{"id": number + 10, "courtType": "SUPREME", "textContent": "<p>Bez kwoty.</p>", "extra": [None, 7]}],
            "links": [{"rel": "next", "href": "next"}] if number == 0 else [],
            "queryTemplate": {key: {"value": [value] if key == "judgmentTypes" else value} for key, value in download.api.search_parameters(params).items()},
            "unknown": {"preserved": True},
        }

    monkeypatch.setattr(download.api, "search_courts", courts)
    monkeypatch.setattr(download.api, "search_judgments", judgments)
    return load_config(overrides={"download_path": "raw", "max_gib": 0, "debug": False, "timeout": 60}), calls


@pytest.mark.parametrize("absolute", [False, True])
def test_raw_pages_preserve_all_data_and_share_session(raw_download, tmp_path, absolute):
    """Retain unrelated cases and unknown fields without loading extraction.

    args:
        raw_download: Mock HTTP setup.
        tmp_path: Isolated output root.
        absolute: Whether to use an absolute download destination.

    returns:
        None.
    """
    config, calls = raw_download
    if absolute:
        config["download_path"] = str(tmp_path / "raw")
    download.download(config)
    page = read_page(page_path(tmp_path / "raw", "judgments", 0))
    assert page["items"][0]["textContent"] == "<p>Bez kwoty.</p>"
    assert page["items"][0]["extra"] == [None, 7]
    assert page["unknown"] == {"preserved": True}
    assert len({id(call[2]) for call in calls}) == 1
    assert all(call[3] == 60 for call in calls)
    state = checkpoints.load_raw_checkpoint(config)
    assert state["page"] == 2 and state["complete"]
    assert {path.name for path in (tmp_path / "raw").iterdir()} == {"checkpoint.json", "common_courts", "judgments"}


def test_http_failure_resumes_only_unsaved_page(raw_download, monkeypatch, tmp_path):
    """Keep committed pages after an external failure.

    args:
        raw_download: Mock HTTP setup.
        monkeypatch: Scoped overrides.
        tmp_path: Isolated output root.

    returns:
        None.
    """
    config, calls = raw_download
    original = download.api.search_judgments

    def fail_second(params, **kwargs):
        """Fail once the first page is committed.

        args:
            params: Requested query.
            kwargs: HTTP controls.

        returns:
            First page or an explicit timeout.
        """
        if params["pageNumber"] == 1:
            raise requests.Timeout("interrupted")
        return original(params, **kwargs)

    monkeypatch.setattr(download.api, "search_judgments", fail_second)
    with pytest.raises(requests.Timeout):
        download.download(config)
    assert checkpoints.load_raw_checkpoint(config)["page"] == 1
    before = page_path(tmp_path / "raw", "judgments", 0).read_bytes()
    monkeypatch.setattr(download.api, "search_judgments", original)
    calls.clear()
    download.download(config)
    assert [(call[0], call[1]) for call in calls] == [("judgment", 1)]
    assert page_path(tmp_path / "raw", "judgments", 0).read_bytes() == before


def test_page_saved_before_checkpoint_is_reused(raw_download, monkeypatch):
    """Recover a durable page without requesting it again.

    args:
        raw_download: Mock HTTP setup.
        monkeypatch: Scoped overrides.

    returns:
        None.
    """
    config, calls = raw_download
    original = download.save_checkpoint

    def interrupted(directory, state):
        """Interrupt the first judgment checkpoint write.

        args:
            directory: Output root.
            state: Pending checkpoint.

        returns:
            None.
        """
        if state["page"] == 1:
            raise OSError("checkpoint interrupted")
        original(directory, state)

    monkeypatch.setattr(download, "save_checkpoint", interrupted)
    with pytest.raises(OSError):
        download.download(config)
    assert checkpoints.load_raw_checkpoint(config)["page"] == 0
    monkeypatch.setattr(download, "save_checkpoint", original)
    calls.clear()
    download.download(config)
    assert [(call[0], call[1]) for call in calls] == [("judgment", 1)]


def test_raw_resume_allows_operational_changes_but_pins_dates(raw_download):
    """Allow page-limit extension while protecting dataset date bounds.

    args:
        raw_download: Mock HTTP setup.

    returns:
        None.
    """
    config, calls = raw_download
    config["max_pages"] = 1
    download.download(config)
    state = checkpoints.load_raw_checkpoint(config)
    assert not state["complete"] and state["page"] == 1
    download.download({**config, "max_pages": 2, "debug": True, "timeout": 12, "max_gib": 1})
    assert checkpoints.load_raw_checkpoint(config)["complete"]
    assert calls[-1][1] == 1 and calls[-1][3] == 12
    with pytest.raises(ValueError, match="date settings changed"):
        checkpoints.load_raw_checkpoint({**config, "max_age_years": 5})


def test_failed_page_write_does_not_advance(raw_download, monkeypatch):
    """Leave the cursor retryable when a page cannot become durable.

    args:
        raw_download: Mock HTTP setup.
        monkeypatch: Scoped overrides.

    returns:
        None.
    """
    config, _ = raw_download
    original = download.write_page

    def fail_judgment(path, payload):
        """Reject judgment writes after saving courts.

        args:
            path: Destination.
            payload: Raw response.

        returns:
            None.
        """
        if path.parent.name == "judgments":
            raise OSError("disk unavailable")
        original(path, payload)

    monkeypatch.setattr(download, "write_page", fail_judgment)
    with pytest.raises(OSError):
        download.download(config)
    assert checkpoints.load_raw_checkpoint(config)["page"] == 0


def test_raw_size_limit_and_legacy_artifacts_are_preserved(raw_download, tmp_path):
    """Refuse oversized output and unrelated preexisting artifacts.

    args:
        raw_download: Mock HTTP setup.
        tmp_path: Isolated output root.

    returns:
        None.
    """
    config, _ = raw_download
    download.download({**config, "max_gib": 1 / 1024**3})
    assert sum(path.stat().st_size for path in (tmp_path / "raw").rglob("*") if path.is_file()) <= 1
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "checkpoint.json").write_text(json.dumps({"page": 3}))
    with pytest.raises(ValueError, match="raw checkpoint"):
        download.download({**config, "download_path": "legacy"})
    assert json.loads((legacy / "checkpoint.json").read_text()) == {"page": 3}


def test_search_filter_is_pinned_and_legacy_downloads_are_preserved(raw_download, tmp_path):
    """Reject query changes and old unfiltered checkpoints without rewriting data.

    args:
        raw_download: Isolated download and HTTP fixture.
        tmp_path: Temporary dataset root.

    returns:
        None.
    """
    config, _ = raw_download
    download.download(config)
    path = tmp_path / "raw/checkpoint.json"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="query or date settings changed"):
        download.download({**config, "search_query": "inna fraza"})
    assert path.read_bytes() == before
    state = json.loads(before)
    for key in ("all", "courtType", "judgmentTypes", "sortingField", "sortingDirection"):
        state["request"].pop(key)
    path.write_text(json.dumps(state))
    legacy = path.read_bytes()
    with pytest.raises(ValueError, match="different download_path"):
        download.download(config)
    assert path.read_bytes() == legacy
