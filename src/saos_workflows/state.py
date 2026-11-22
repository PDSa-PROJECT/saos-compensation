"""Single-writer local recovery journal, separate from legacy checkpoints.

This is within-attempt recovery only, not successful-artifact caching or publication.
Callers supply already computed configuration/model/source fingerprints, including
relevant code and prompt revisions. Existing core output limits apply when active;
this journal does not measure remote artifact storage or implement a cloud budget.
"""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from saos_dataset.storage.files import write_json


@dataclass(frozen=True)
class RecoveryIdentity:
    """All compatibility keys required to resume one stage attempt."""

    stage: str
    input_version: str
    config_hash: str
    model_identity: str
    source_identity: str

    def __post_init__(self):
        """Require explicit identities and a filesystem-safe stage name.

        args:
            self: Recovery compatibility identity.
        returns:
            None.
        """
        if any(not isinstance(value, str) or not value.strip() for value in asdict(self).values()):
            raise ValueError("Recovery identity fields must be nonempty strings")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.stage):
            raise ValueError("Recovery stage must be a lowercase identifier")


class RecoveryState:
    """Append durable JSON results before progress; use one writer per workspace."""

    def __init__(self, workspace, identity):
        """Open a dedicated stage namespace and recover interrupted progress writes.

        args:
            self: Journal being opened.
            workspace: Explicit new-workflow workspace, not a legacy output folder.
            identity: Full compatible stage/input/config/model/source identity.
        returns:
            None.
        """
        if not isinstance(identity, RecoveryIdentity):
            raise TypeError("identity must be a RecoveryIdentity")
        self.identity = identity
        self.directory = Path(workspace) / "workflow-recovery" / identity.stage
        identity_path = self.directory / "identity.json"
        expected = {"version": 1, "identity": asdict(identity)}
        if identity_path.exists():
            if self._read(identity_path) != expected:
                raise ValueError("Incompatible recovery state; use a new workspace")
        else:
            if self.directory.exists() and any(self.directory.iterdir()):
                raise ValueError("Recovery workspace has data but no identity")
            write_json(identity_path, expected)
        self._results = {}
        result_paths = sorted((self.directory / "results").glob("*.json"))
        for index, path in enumerate(result_paths):
            saved = self._read(path)
            if (
                path.name != f"{index:012d}.json"
                or not isinstance(saved, dict)
                or set(saved) != {"item_id", "result"}
                or not isinstance(saved["item_id"], str)
                or not saved["item_id"].strip()
                or saved["item_id"] in self._results
            ):
                raise ValueError("Invalid durable recovery result")
            self._results[saved["item_id"]] = path
        progress_path = self.directory / "progress.json"
        completed = list(self._results)
        progress = self._read(progress_path) if progress_path.exists() else {"completed": []}
        if (
            not isinstance(progress, dict)
            or set(progress) != {"completed"}
            or not isinstance(progress["completed"], list)
            or progress["completed"] != completed[:len(progress["completed"])]
        ):
            raise ValueError("Recovery progress does not match durable results")
        if progress["completed"] != completed:
            write_json(progress_path, {"completed": completed})

    @staticmethod
    def _read(path):
        """Read journal JSON without concealing malformed or missing files.

        args:
            path: Journal file to read.
        returns:
            Parsed JSON value.
        """
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def completed_ids(self):
        """Expose durable completion order without allowing caller mutation.

        args:
            self: Open journal.
        returns:
            Tuple of completed item identifiers.
        """
        return tuple(self._results)

    def get_result(self, item_id):
        """Read a completed result independently of the legacy decision cache.

        args:
            self: Open journal.
            item_id: Completed item identifier; missing IDs raise KeyError.
        returns:
            Detached JSON result suitable for reuse after restart.
        """
        return self._read(self._results[item_id])["result"]

    def complete(self, item_id, result):
        """Persist a completed result atomically before advancing its progress.

        args:
            self: Open single-writer journal.
            item_id: Stable identifier of the completed item.
            result: JSON-serializable result; operational failures must be raised instead.
        returns:
            None.
        """
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("Completed item ID must be a nonempty string")
        result = json.loads(json.dumps(result, allow_nan=False))
        if item_id in self._results:
            if self.get_result(item_id) != result:
                raise ValueError("Completed recovery results are immutable")
        else:
            path = self.directory / "results" / f"{len(self._results):012d}.json"
            write_json(path, {"item_id": item_id, "result": result})
            self._results[item_id] = path
        write_json(self.directory / "progress.json", {"completed": list(self._results)})
