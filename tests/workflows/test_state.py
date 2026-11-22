"""Durable per-item recovery without legacy checkpoint or artifact publication."""

import json
from dataclasses import replace

import pytest

from saos_workflows import state
from saos_workflows.state import RecoveryIdentity, RecoveryState


@pytest.fixture
def identity():
    """Provide explicit compatibility keys for a fixture-only attempt.

    args:
        None.
    returns:
        Stage recovery identity.
    """
    return RecoveryIdentity("extract_features", "artifact:version-1", "config-hash", "model-revision-engine-prompt", "source-locality-code-hash")


def test_restart_reuses_durable_results_without_legacy_writes(tmp_path, identity):
    """Read the same completed values and preserve unrelated legacy files.

    args:
        tmp_path: Isolated workspace.
        identity: Complete compatibility identity.
    returns:
        None.
    """
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text('{"legacy": true}', encoding="utf-8")
    journal = RecoveryState(tmp_path, identity)
    result = {"eligible": False, "rejection_reasons": ["missing_target"], "amount": None}
    journal.complete("254930", result)
    result["eligible"] = True
    restarted = RecoveryState(tmp_path, identity)
    assert restarted.completed_ids == ("254930",)
    assert restarted.get_result("254930")["eligible"] is False
    assert restarted.get_result("254930")["amount"] is None
    detached = restarted.get_result("254930")
    detached["eligible"] = True
    assert restarted.get_result("254930")["eligible"] is False
    restarted.complete("254931", {"eligible": True})
    assert RecoveryState(tmp_path, identity).completed_ids == ("254930", "254931")
    assert checkpoint.read_text(encoding="utf-8") == '{"legacy": true}'
    with pytest.raises(KeyError):
        restarted.get_result("missing")


@pytest.mark.parametrize("field", ["input_version", "config_hash", "model_identity", "source_identity"])
def test_incompatible_resume_fails_without_modification(tmp_path, identity, field):
    """Reject reuse when any non-stage identity key changes.

    args:
        tmp_path: Recovery workspace.
        identity: Original attempt identity.
        field: Compatibility key to change.
    returns:
        None.
    """
    journal = RecoveryState(tmp_path, identity)
    journal.complete("1", {"value": 1})
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    with pytest.raises(ValueError, match="Incompatible recovery"):
        RecoveryState(tmp_path, replace(identity, **{field: "changed"}))
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.json")} == before


def test_stages_use_separate_namespaces(tmp_path, identity):
    """Prevent one stage's progress from being interpreted as another's.

    args:
        tmp_path: Shared workflow workspace.
        identity: Feature-stage identity.
    returns:
        None.
    """
    first = RecoveryState(tmp_path, identity)
    first.complete("1", {"stage": "features"})
    second = RecoveryState(tmp_path, replace(identity, stage="find_targets"))
    assert second.completed_ids == ()
    assert first.directory != second.directory


@pytest.mark.parametrize("failed_file", ["progress.json", "000000000000.json"])
def test_interruption_preserves_result_before_progress(tmp_path, identity, monkeypatch, failed_file):
    """Recover a durable orphan but never invent a result after a failed write.

    args:
        tmp_path: Recovery workspace.
        identity: Attempt identity.
        monkeypatch: Atomic-writer failure injection.
        failed_file: Result or progress write to interrupt.
    returns:
        None.
    """
    journal = RecoveryState(tmp_path, identity)
    original = state.write_json
    writes = []

    def interrupted_write(path, value):
        """Interrupt the selected write before it becomes durable.

        args:
            path: Output file requested by the journal.
            value: Serialized journal data.
        returns:
            None.
        """
        writes.append(path.name)
        if path.name == failed_file:
            raise OSError("interrupted")
        original(path, value)

    monkeypatch.setattr(state, "write_json", interrupted_write)
    with pytest.raises(OSError, match="interrupted"):
        journal.complete("1", {"completed": True})
    monkeypatch.setattr(state, "write_json", original)
    restarted = RecoveryState(tmp_path, identity)
    if failed_file == "progress.json":
        assert writes == ["000000000000.json", "progress.json"]
        assert restarted.completed_ids == ("1",)
        assert restarted.get_result("1") == {"completed": True}
    else:
        assert writes == ["000000000000.json"]
        assert restarted.completed_ids == ()
        restarted.complete("1", {"completed": True})
    assert RecoveryState(tmp_path, identity).completed_ids == ("1",)


def test_progress_cannot_reference_missing_results(tmp_path, identity):
    """Fail loudly if a previously committed result has been lost.

    args:
        tmp_path: Recovery workspace.
        identity: Attempt identity.
    returns:
        None.
    """
    journal = RecoveryState(tmp_path, identity)
    state.write_json(journal.directory / "progress.json", {"completed": ["missing"]})
    with pytest.raises(ValueError, match="progress does not match"):
        RecoveryState(tmp_path, identity)


def test_results_are_immutable_and_invalid_json_never_advances(tmp_path, identity):
    """Keep completed results stable and reject non-finite JSON before writing.

    args:
        tmp_path: Recovery workspace.
        identity: Attempt identity.
    returns:
        None.
    """
    journal = RecoveryState(tmp_path, identity)
    with pytest.raises(ValueError):
        journal.complete("bad", {"value": float("nan")})
    assert journal.completed_ids == ()
    journal.complete("1", {"value": 1})
    journal.complete("1", {"value": 1})
    with pytest.raises(ValueError, match="immutable"):
        journal.complete("1", {"value": 2})
    assert json.loads((journal.directory / "progress.json").read_text())["completed"] == ["1"]
