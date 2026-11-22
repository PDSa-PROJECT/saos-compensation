"""Basic durable workflow recovery check."""

from dataclasses import replace

import pytest

from saos_workflows.state import RecoveryIdentity, RecoveryState


def test_recovery_restarts_and_rejects_incompatible_settings(tmp_path):
    """Read one durable result without changing the legacy checkpoint.

    args:
        tmp_path: Isolated workflow workspace.
    returns:
        None.
    """
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text('{"legacy": true}', encoding="utf-8")
    identity = RecoveryIdentity("features", "input-v1", "config-v1", "model-v1", "source-v1")
    RecoveryState(tmp_path, identity).complete("123", {"eligible": False})
    restarted = RecoveryState(tmp_path, identity)
    assert restarted.completed_ids == ("123",)
    assert restarted.get_result("123") == {"eligible": False}
    with pytest.raises(ValueError, match="Incompatible recovery"):
        RecoveryState(tmp_path, replace(identity, config_hash="config-v2"))
    assert checkpoint.read_text(encoding="utf-8") == '{"legacy": true}'
