"""Local selection and processing progress independently of SAOS transport."""

import copy

import pytest

from dataset.acquisition.settings import load_config as acquisition_config
from dataset.extraction.model.configuration import load_config
from dataset.processing import source
from dataset.storage import checkpoints
from dataset.storage.files import write_json
from dataset.storage.raw import page_path, read_page, write_page


@pytest.fixture
def local_source(output_root, judgment_payload):
    """Populate the isolated raw snapshot with selected and unrelated cases.

    args:
        output_root: Isolated source and output directories.
        judgment_payload: Valid judgment metadata and original HTML.

    returns:
        Processing configuration and expected source payload.
    """
    data = judgment_payload["data"]
    write_json(page_path(output_root / "tmp/raw", "common_courts", 0), {
        "items": [{**data["division"]["court"], "divisions": [{"id": 10, "name": "I Wydział Cywilny"}]}], "links": [],
    })
    write_json(page_path(output_root / "tmp/raw", "judgments", 0), {
        "items": [{"id": 8, "courtType": "SUPREME"}, data, {"id": 9, "courtType": "COMMON", "judgmentType": "SENTENCE", "textContent": "Inna sprawa."}],
        "links": [],
    })
    return load_config(), data


def test_processing_joins_metadata_and_never_changes_raw(local_source, output_root, monkeypatch):
    """Select cases locally and advance a rejected extraction without deleting input.

    args:
        local_source: Configuration and saved source judgment.
        output_root: Isolated root.
        monkeypatch: Scoped network guard.

    returns:
        None.
    """
    monkeypatch.setattr("requests.Session.request", lambda *args, **kwargs: pytest.fail("Processing requested SAOS"))
    config, data = local_source
    paths = list((output_root / "tmp/raw").rglob("*.json"))
    before = {path: path.read_bytes() for path in paths}
    state = checkpoints.load_checkpoint(config)
    stream = source.records_from_raw(config["processing"], state, "test")
    record = next(stream)
    assert record["id"] == data["id"]
    assert record["source_payload"] == data
    assert record["division"]["court"]["type"] == "REGIONAL"
    assert "<p>" not in record["text"]
    assert state["next_item"] == 1
    record["rejected"] = True
    assert list(stream) == []
    assert state["complete"] and state["page"] == 1
    assert {path: path.read_bytes() for path in paths} == before


def test_processing_cannot_advance_without_durable_result(local_source):
    """Retry an interrupted case instead of silently losing it.

    args:
        local_source: Configuration and saved source judgment.

    returns:
        None.
    """
    config, data = local_source
    state = checkpoints.load_checkpoint(config)
    stream = source.records_from_raw(config["processing"], state, "first")
    assert next(stream)["id"] == data["id"]
    with pytest.raises(RuntimeError, match="completed record"):
        next(stream)
    saved = checkpoints.load_checkpoint(config)
    assert saved["page"] == 0 and saved["next_item"] == 1
    retry = source.records_from_raw(config["processing"], saved, "retry")
    assert next(retry)["id"] == data["id"]
    retry.close()


def test_saved_result_and_duplicates_are_not_processed_again(local_source, output_root):
    """Recognize completed output and deduplicate IDs across raw pages.

    args:
        local_source: Configuration and saved source judgment.
        output_root: Isolated root.

    returns:
        None.
    """
    config, data = local_source
    raw = output_root / "tmp/raw"
    raw_state = read_page(page_path(raw, "judgments", 0))
    write_json(page_path(raw, "judgments", 1), raw_state)
    import json

    checkpoint = json.loads((raw / "checkpoint.json").read_text())
    checkpoint["page"] = 2
    write_json(raw / "checkpoint.json", checkpoint)
    state = checkpoints.load_checkpoint(config)
    stream = source.records_from_raw(config["processing"], state, "first")
    assert next(stream)["id"] == data["id"]
    stream.close()
    folder = output_root / "tmp/processed" / str(data["id"])
    write_json(folder / "record.json", {"feature": "value"})
    write_json(folder / "award.json", {"total": 10000, "valid": True})
    saved = checkpoints.load_checkpoint(config)
    assert list(source.records_from_raw(config["processing"], saved, "retry")) == []
    assert saved["page"] == 2 and saved["complete"]


def test_processing_snapshot_rejects_changed_raw_and_settings(local_source, output_root):
    """Keep extraction experiments independent of raw acquisition state.

    args:
        local_source: Configuration and saved source judgment.
        output_root: Isolated root.

    returns:
        None.
    """
    config, _ = local_source
    checkpoint = checkpoints.load_checkpoint(config)
    checkpoints.save_checkpoint(output_root / "tmp/processed", checkpoint)
    changed = copy.deepcopy(config)
    changed["chunk_characters"] += 1
    with pytest.raises(ValueError, match="Extraction settings changed"):
        checkpoints.load_checkpoint(changed)
    path = page_path(output_root / "tmp/raw", "judgments", 0)
    payload = read_page(path)
    payload["unknown"] = True
    write_json(path, payload)
    with pytest.raises(ValueError, match="Raw input snapshot changed"):
        checkpoints.load_checkpoint(config)
    assert checkpoints.load_raw_checkpoint({**acquisition_config(), "download_path": "tmp/raw"})["complete"]
    assert checkpoints.load_checkpoint({**config, "processing": {**config["processing"], "output_path": "another"}})["page"] == 0


@pytest.mark.parametrize("defect", ["type", "name", "division", "duplicate"])
def test_invalid_court_metadata_is_rejected_in_processing(judgment_payload, defect):
    """Validate semantic metadata only when preparing extraction inputs.

    args:
        judgment_payload: Court and division metadata.
        defect: Invalid metadata field.

    returns:
        None.
    """
    data = judgment_payload["data"]
    court = {**data["division"]["court"], "divisions": [{"id": 10, "name": "Civil"}]}
    if defect == "type":
        court["type"] = "OTHER"
    elif defect == "name":
        court["name"] = ""
    elif defect == "division":
        court["divisions"][0]["id"] = True
    else:
        court["divisions"] *= 2
    with pytest.raises(ValueError):
        source.read_divisions([{"items": [court], "links": []}])


def test_raw_pages_cannot_be_overwritten(local_source, output_root):
    """Keep the immutable raw source when another response differs.

    args:
        local_source: Saved raw snapshot.
        output_root: Isolated root.

    returns:
        None.
    """
    path = page_path(output_root / "tmp/raw", "judgments", 0)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="different data"):
        write_page(path, {"items": [], "links": []})
    assert path.read_bytes() == before


def test_processing_reads_and_resumes_absolute_paths(local_source, output_root):
    """Read raw pages and save processing progress at absolute filesystem locations.

    args:
        local_source: Saved raw snapshot with one selected judgment.
        output_root: Isolated input/output location.

    returns:
        None.
    """
    _, data = local_source
    destination = output_root / "processed with spaces"
    config = load_config(overrides={
        "input_path": str(output_root / "tmp/raw"),
        "output_path": str(destination),
        "max_gib": 0,
    })
    state = checkpoints.load_checkpoint(config)
    stream = source.records_from_raw(config["processing"], state, "absolute")
    record = next(stream)
    assert record["id"] == data["id"]
    record["rejected"] = True
    assert list(stream) == []
    assert (destination / "checkpoint.json").is_file()
    resumed = checkpoints.load_checkpoint(config)
    assert resumed["complete"] and resumed["page"] == 1
