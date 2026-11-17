"""Processing output isolation and lightweight extraction dependencies."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from dataset.processing import pipeline, source
from dataset.storage import checkpoints
from dataset.storage.files import write_json
from dataset.acquisition.settings import load_config, search_settings


@pytest.fixture
def output_root(monkeypatch, tmp_path):
    """Keep pipeline, local source and checkpoint output in one isolated root.

    args:
        monkeypatch: Scoped module configuration overrides.
        tmp_path: Isolated test directory.

    returns:
        Root containing the test dataset and temporary state.
    """
    for module in (pipeline, source, checkpoints):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    raw = tmp_path / "tmp/raw"
    request = search_settings(load_config())[2]
    write_json(raw / "checkpoint.json", {
        "kind": "raw", "dataset_id": "raw-test", "request": request,
        "page": 1, "court_page": 1, "courts_complete": True, "complete": True,
    })
    write_json(raw / "common_courts/00000000.json", {"items": [], "links": []})
    write_json(raw / "judgments/00000000.json", {"items": [], "links": []})
    return tmp_path


@pytest.fixture
def fake_extractor():
    """Supply an extraction context without importing or loading model dependencies.

    args:
        None.

    returns:
        Configurable extraction callable, context and cleanup status.
    """
    client = SimpleNamespace(extract=None, stopped=False)

    @asynccontextmanager
    async def context():
        """Expose the configured extraction callable and record cleanup.

        args:
            None.

        returns:
            Async context yielding the test extraction callable.
        """
        try:
            yield client.extract
        finally:
            client.stopped = True

    client.context = context()
    return client


@pytest.fixture
def record_source():
    """Provide a judgment stream that never opens an external connection.

    args:
        None.

    returns:
        Iterator factory matching the processing pipeline boundary.
    """
    def record_source(*args):
        """Yield one source judgment without external API access.

        args:
            args: Processing settings, checkpoint and run identifier.

        returns:
            Iterator containing one structurally valid source judgment.
        """
        yield {
            "id": 42,
            "text": "Opis.",
            "source_payload": {"id": 42},
            "judgmentDate": "2020-05-12",
            "division": {"court": {"name": "Sąd Okręgowy w Płocku"}},
        }

    return record_source
