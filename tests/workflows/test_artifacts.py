"""Basic Parquet source, target and lazy materializer checks."""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pyarrow.parquet as pq
import pytest
from zenml.artifact_stores.local_artifact_store import LocalArtifactStore, LocalArtifactStoreConfig
from zenml.enums import StackComponentType

from saos_workflows.artifacts import ParquetArtifact, ParquetArtifactMaterializer, write_cases
from saos_workflows.contracts import ArtifactMetadata, Span, TargetContext, source_row


def _metadata():
    """Provide fixed provenance for the small artifact examples.

    args:
        None.
    returns:
        Valid target-stage metadata.
    """
    return ArtifactMetadata(
        stage="targets", queries=["zadośćuczynienie"], date_from=date(2020, 1, 1),
        date_to=date(2020, 12, 31), config_hashes={"targets": "fixture"},
        source_identity="fixture-saos",
    )


def test_parquet_retains_source_rejected_rows_and_exact_money(tmp_path, judgment_payload):
    """Retain IDs and unknown source fields without inventing missing awards.

    args:
        tmp_path: Isolated artifact location.
        judgment_payload: Complete SAOS detail fixture.
    returns:
        None.
    """
    source = {**judgment_payload, "unknownEnvelope": {"retained": True}}
    accepted = source_row(source, judgment_text="Fakty.")
    accepted.update(collection_status="accepted", targets_status="accepted",
                    target_total_pln="10000.01", target_confirmed=True)
    rejected = source_row({**source, "data": {**source["data"], "id": source["data"]["id"] + 1}})
    rejected.update(collection_status="rejected", targets_status="skipped", features_status="skipped",
                    rejection_reasons=["not a compensation case"], eligible=False)
    artifact = write_cases([accepted, rejected], str(tmp_path / "cases"), _metadata())
    rows = pq.read_table(artifact.parquet_uri).to_pylist()
    assert artifact.row_count == 2
    assert [row["saos_id"] for row in rows] == [accepted["saos_id"], rejected["saos_id"]]
    assert json.loads(rows[0]["source_json"])["unknownEnvelope"] == {"retained": True}
    assert rows[0]["target_total_pln"] == Decimal("10000.01")
    assert rows[1]["target_total_pln"] is None and rows[1]["collection_status"] == "rejected"
    with pytest.raises(ValueError, match="Duplicate SAOS ID"):
        write_cases([accepted, accepted], str(tmp_path / "duplicate"), _metadata())


def test_target_context_and_evidence_survive_parquet(tmp_path, judgment_payload):
    """Keep the core target handoff and source offsets across serialization.

    args:
        tmp_path: Isolated artifact location.
        judgment_payload: Complete SAOS detail fixture.
    returns:
        None.
    """
    text = "Zasądza 10 zł. Ból trwał."
    window = {"text": "Zasądza 10 zł.", "start": 0, "end": 14, "similarity": 0.96}
    award = {"suma": "10", "confirmed": True, "request": "brak informacji",
             "injured_party_count": 1, "target_matches": {"judgment": window}}
    row = source_row(judgment_payload, judgment_text=text)
    row.update(collection_status="accepted", targets_status="accepted", target_total_pln="10",
               target_confirmed=True, target_context=TargetContext.from_core(award))
    start = text.index("Ból")
    row["damage_evidence"] = [Span(text="Ból trwał.", start=start, end=len(text))]
    artifact = write_cases([row], str(tmp_path / "context"), _metadata())
    result = pq.read_table(artifact.parquet_uri).to_pylist()[0]
    assert TargetContext.model_validate(result["target_context"]).to_core() == award
    assert result["damage_evidence"][0] == {"text": "Ból trwał.", "start": start, "end": len(text)}


def test_native_materializer_loads_only_the_reference(tmp_path, judgment_payload, monkeypatch):
    """Prove ZenML's local materializer does not eagerly read Parquet.

    args:
        tmp_path: Isolated native artifact location.
        judgment_payload: Complete SAOS detail fixture.
        monkeypatch: Scoped guard against a whole-table read.
    returns:
        None.
    """
    now = datetime.now(timezone.utc)
    store = LocalArtifactStore(
        name="fixture-store", id=uuid4(), user=None, flavor="local",
        type=StackComponentType.ARTIFACT_STORE,
        config=LocalArtifactStoreConfig(path=str(tmp_path / "native-store")), created=now, updated=now,
    )
    source = write_cases([source_row(judgment_payload)], str(tmp_path / "workspace"), _metadata())
    materializer = ParquetArtifactMaterializer(uri=str(tmp_path / "native-store/version-1"), artifact_store=store)
    materializer.save(source)

    def no_table(*args, **kwargs):
        """Reject an eager Parquet read during reference loading.

        args:
            args: Positional arguments from a forbidden read.
            kwargs: Keyword arguments from a forbidden read.
        returns:
            None; always raises.
        """
        raise AssertionError("Artifact load must not read a table")

    monkeypatch.setattr(pq, "read_table", no_table)
    restored = materializer.load(ParquetArtifact)
    assert restored.row_count == 1 and restored.schema == source.schema
    assert restored.parquet_uri.endswith("/cases.parquet")
