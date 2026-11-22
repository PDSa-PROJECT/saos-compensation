"""Fixture-only judgment contracts, exact amounts and native ZenML publication."""

import copy
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from zenml.artifact_stores.local_artifact_store import LocalArtifactStore, LocalArtifactStoreConfig
from zenml.enums import StackComponentType

from saos_workflows.artifacts import (
    ParquetArtifact, ParquetArtifactMaterializer, load_artifact, write_cases,
)
from saos_workflows.contracts import (
    ArtifactMetadata, MONEY_TYPE, Review, Span, TargetContext, case_schema,
    money, predictor_fields, source_row,
)


@pytest.fixture
def metadata():
    """Create provenance independent of live SAOS, models or a ZenML server.

    args:
        None.
    returns:
        Target-stage artifact metadata.
    """
    return ArtifactMetadata(
        stage="targets", queries=["zadośćuczynienie", "odszkodowanie"], phrase_match="any",
        date_from=date(2020, 1, 1), date_to=date(2020, 12, 31), record_limit=10,
        config_hashes={"targets": "fixture-target-hash"}, source_identity="fixture-saos",
        input_artifact_id="explicit-collection-version",
    )


@pytest.fixture
def core_award():
    """Provide all current role keys and separately supported principal anchors.

    args:
        None.
    returns:
        Existing core award shape, with tuple classes and missing request money.
    """
    text = "Zasądza 10 000,01 zł na rzecz A. B."
    amount = {
        "text": text, "start": 0, "end": len(text),
        "amount_start": 8, "amount_end": 20,
        "sentence": {"text": text, "start": 0, "end": len(text)},
        "classes": ("judgment", "other_payments"), "operative": True,
        "first_amount": True, "procedural": False, "similarity": 0.96,
        "pattern": "Zasądza kwotę zadośćuczynienia",
    }
    return {
        "suma": "10000.01", "confirmed": True, "request": "brak informacji",
        "injured_party_count": 1, "beneficiaries": ["A. B."],
        "status": "amount parsed from embedding-selected judgment sentence",
        "target_matches": {
            "judgment": {**amount, "awards": [amount]}, "request": None,
            "judgment-denial": None, "prior_payment": amount,
            "procedural_costs": None, "mixed": None, "other_payments": None,
        },
    }


@pytest.fixture
def local_store(tmp_path):
    """Construct the pinned native local artifact store without persistent setup.

    args:
        tmp_path: Isolated fixture filesystem root.
    returns:
        Real ZenML LocalArtifactStore, not a mock storage implementation.
    """
    now = datetime.now(timezone.utc)
    return LocalArtifactStore(
        name="fixture-store", id=uuid4(), user=None, flavor="local",
        type=StackComponentType.ARTIFACT_STORE,
        config=LocalArtifactStoreConfig(path=str(tmp_path / "native-store")),
        created=now, updated=now,
    )


def test_plain_parquet_conserves_ids_source_nulls_and_statuses(tmp_path, metadata, judgment_payload):
    """Keep accepted and rejected identities, unknown envelope fields and typed nulls.

    args:
        tmp_path: Isolated output directory.
        metadata: Artifact provenance fixture.
        judgment_payload: Complete source envelope fixture.
    returns:
        None.
    """
    source = copy.deepcopy(judgment_payload)
    source.update(unknownEnvelope={"nested": [1, None, {"new": True}]})
    source["data"]["id"] = 2**53 + 1
    source["data"]["futureField"] = ["ą", {"retained": True}]
    first = source_row(source, judgment_text="Fakty.", matched_phrases=["a", "a", "b"])
    first.update(collection_status="accepted", cause="not_available", prior_payment=0)
    source["data"]["id"] += 1
    second = source_row(source)
    second.update(collection_status="rejected", targets_status="skipped", features_status="skipped",
                  rejection_reasons=["no eligible monetary clause"], eligible=False)
    artifact = write_cases([first, second], str(tmp_path / "cases"), metadata, batch_size=1)
    table = pq.read_table(artifact.parquet_uri)
    rows = table.to_pylist()
    # Compliant Parquet normalizes Arrow list child names from item to element.
    assert table.schema.equals(case_schema())
    assert table.schema.metadata == case_schema().metadata
    assert table.schema.field("target_total_pln").type == MONEY_TYPE
    assert table.schema.field("cause").type == pa.string()
    assert artifact.row_count == 2
    assert table["saos_id"].to_pylist() == [2**53 + 1, 2**53 + 2]
    assert json.loads(rows[0]["source_json"])["unknownEnvelope"] == source["unknownEnvelope"]
    assert json.loads(rows[0]["source_json"])["data"]["futureField"] == source["data"]["futureField"]
    assert rows[0]["cause"] is None and rows[0]["prior_payment"] == 0
    assert rows[0]["target_total_pln"] is None
    assert rows[0]["matched_phrases"] == ["a", "b"]
    assert rows[1]["collection_status"] == "rejected" and rows[1]["eligible"] is False
    assert "source_json" not in predictor_fields(metadata)
    assert "target_total_pln" not in predictor_fields(metadata)
    assert "config_hashes" not in table.column_names and "queries" not in table.column_names
    assert load_artifact(artifact.uri).metadata == metadata
    assert load_artifact(artifact.uri).metadata.phrase_match == "any"


@pytest.mark.parametrize("value", ["0", "10000.01", "999999999999999999999999999999999999.99", "1.2300"])
def test_exact_money(value):
    """Accept exactly representable grosz values independently of Decimal context.

    args:
        value: Boundary monetary string.
    returns:
        None.
    """
    assert money(value) == Decimal(value)


@pytest.mark.parametrize("value", ["0.001", "1e36", "NaN", "Infinity", "-0.01", 0.1, True])
def test_unrepresentable_money_rejected(value):
    """Reject silent rounding, overflow, nonfinite values and binary floats.

    args:
        value: Invalid or unrepresentable monetary input.
    returns:
        None.
    """
    with pytest.raises(ValueError):
        money(value)


def test_target_context_and_nested_reviews_roundtrip(tmp_path, metadata, judgment_payload, core_award):
    """Preserve complete target handoffs, multi-span evidence and associated answers.

    args:
        tmp_path: Isolated artifact root.
        metadata: Artifact provenance fixture.
        judgment_payload: Complete detail response fixture.
        core_award: Existing core target dictionary fixture.
    returns:
        None.
    """
    award = TargetContext.from_core(core_award)
    assert award.to_core() == core_award
    text = core_award["target_matches"]["judgment"]["text"] + " Ból trwał. Nie mógł pracować."
    row = source_row(judgment_payload, judgment_text=text)
    row.update(collection_status="accepted", targets_status="accepted", features_status="rejected",
               target_total_pln=core_award["suma"], target_confirmed=True, target_context=award,
               eligible=False, rejection_reasons=["no source-backed damage description"])
    spans = [
        Span(text="Ból trwał.", start=text.index("Ból"), end=text.index("Ból") + 10),
        Span(text="Nie mógł pracować.", start=text.index("Nie"), end=len(text)),
    ]
    row["limitations_evidence"] = spans
    row["limitations"] = " ".join(span.text for span in spans)
    review = Review.from_core({
        "text": text[spans[0].start:], "start": spans[0].start, "end": len(text),
        "accepted": True, "rejection_reasons": [],
        "answers": {
            "sekcja": {"choice": "fakty", "confidence": 0.98, "probabilities": {"fakty": 0.98, "inne": 0.02}},
            "wyciek": {"noul": 0.01, "probabilities": {"true": 0.01, "false": 0.99}},
            "fit_limitations": {"noul": 0.95, "probabilities": {"true": 0.95, "false": 0.05}},
        },
    })
    row["limitations_reviews"] = [review]
    artifact = write_cases([row], str(tmp_path / "nested"), metadata)
    restored = pq.read_table(artifact.parquet_uri).to_pylist()[0]
    assert restored["target_total_pln"] == Decimal("10000.01")
    assert restored["target_confirmed"] is True and restored["eligible"] is False
    assert TargetContext.model_validate(restored["target_context"]).to_core() == core_award
    assert restored["limitations_evidence"] == [span.model_dump() for span in spans]
    answers = restored["limitations_reviews"][0]["answers"]
    assert answers[0]["choice"] == "fakty" and answers[0]["confidence"] == 0.98
    assert answers[1]["noul"] == 0.01 and answers[2]["noul"] == 0.95
    assert dict(answers[1]["probabilities"]) == {"true": 0.01, "false": 0.99}
    assert artifact.scan().select("saos_id", "target_total_pln").collect().height == 1
    carried = write_cases([restored], str(tmp_path / "carried-forward"), metadata)
    assert carried.row_count == 1


@pytest.mark.parametrize("count", [None, "not_available", "brak informacji", 3])
def test_missing_target_handoff_roundtrip(count):
    """Distinguish missing money/counts from a confirmed zero denial.

    args:
        count: Existing missing marker or source-supported recipient count.
    returns:
        None.
    """
    award = {
        "suma": "brak informacji", "confirmed": False, "request": "brak informacji",
        "injured_party_count": count, "status": "no matching judgment sentence",
        "target_matches": {"judgment": None, "excluded_reason": "appeal contains no new principal award"},
        "excluded": True,
    }
    assert TargetContext.from_core(award).to_core() == award
    assert money(award["suma"]) is None
    assert money("0") == Decimal("0.00")


def test_duplicate_ids_and_wrong_source_fail_without_completion(tmp_path, metadata, judgment_payload):
    """Never silently deduplicate or publish a table after malformed input.

    args:
        tmp_path: Isolated artifact workspace.
        metadata: Artifact metadata fixture.
        judgment_payload: Source fixture.
    returns:
        None.
    """
    row = source_row(judgment_payload)
    with pytest.raises(ValueError, match="Duplicate SAOS ID"):
        write_cases([row, row], str(tmp_path / "duplicates"), metadata, batch_size=1)
    assert not (tmp_path / "duplicates/reference.json").exists()
    with pytest.raises(ValueError, match="Source envelope ID"):
        write_cases([{**row, "saos_id": row["saos_id"] + 1}], str(tmp_path / "wrong"), metadata)


def test_native_materializer_roundtrip_is_reference_only(tmp_path, metadata, judgment_payload, local_store, monkeypatch):
    """Publish through real ZenML IO and prove load never reads the Parquet table.

    args:
        tmp_path: Fixture workspace.
        metadata: Artifact provenance fixture.
        judgment_payload: Complete SAOS detail fixture.
        local_store: Native ZenML local artifact store.
        monkeypatch: Scoped IO guards.
    returns:
        None.
    """
    source = write_cases([source_row(judgment_payload)], str(tmp_path / "workspace"), metadata)
    uri = str(tmp_path / "native-store/version-1")
    materializer = ParquetArtifactMaterializer(uri=uri, artifact_store=local_store)
    materializer.save(source)
    assert pq.read_table(f"{uri}/cases.parquet").num_rows == 1
    opened = []
    original_open = local_store.open

    def manifest_only(path, mode="r"):
        """Fail if materializer load attempts any Parquet access.

        args:
            path: Native store path requested by the loader.
            mode: Requested stream mode.
        returns:
            Manifest stream only.
        """
        opened.append(path)
        assert str(path).endswith("reference.json")
        return original_open(path, mode)

    def no_table(*args, **kwargs):
        """Reject eager table APIs during reference deserialization.

        args:
            args: Forbidden eager API positional arguments.
            kwargs: Forbidden eager API keyword arguments.
        returns:
            None; always raises AssertionError.
        """
        raise AssertionError("Artifact load must not materialize a table")

    monkeypatch.setattr(local_store, "open", manifest_only)
    monkeypatch.setattr(pq, "read_table", no_table)
    monkeypatch.setattr(pl, "read_parquet", no_table)
    restored = materializer.load(ParquetArtifact)
    assert restored.parquet_uri == f"{uri}/cases.parquet"
    assert restored.row_count == 1 and restored.metadata == metadata
    assert restored.schema == source.schema and len(opened) == 1


def test_completed_artifact_is_not_overwritten(tmp_path, metadata, judgment_payload):
    """Require new artifact versions rather than destructive rewrites.

    args:
        tmp_path: Isolated workspace root.
        metadata: Artifact provenance fixture.
        judgment_payload: Complete source fixture.
    returns:
        None.
    """
    uri = str(tmp_path / "immutable")
    write_cases([source_row(judgment_payload)], uri, metadata)
    with pytest.raises(FileExistsError):
        write_cases([], uri, metadata)


@pytest.mark.parametrize("total", [None, "0", "999999999999999999999999999999999999.99"])
def test_decimal_and_null_parquet_boundaries(tmp_path, metadata, judgment_payload, local_store, total):
    """Round-trip missing, zero-denial and maximum exact values via native store IO.

    args:
        tmp_path: Isolated fixture output root.
        metadata: Artifact provenance fixture.
        judgment_payload: Complete source fixture.
        local_store: Native ZenML artifact store.
        total: Exact PLN boundary or missing value.
    returns:
        None.
    """
    row = source_row(judgment_payload)
    row["target_total_pln"] = total
    row["target_confirmed"] = total is not None
    artifact = write_cases([row], str(tmp_path / "native-store/decimal"), metadata, artifact_store=local_store)
    with local_store.open(artifact.parquet_uri, "rb") as stream:
        result = pq.read_table(stream).to_pylist()[0]
    assert result["target_total_pln"] == (Decimal(total) if total is not None else None)
    assert result["eligible"] is None


@pytest.mark.parametrize("changes", [
    {"saos_id": True}, {"saos_id": "254930"}, {"saos_id": 2**63},
    {"prior_payment": 1.5}, {"injured_party_count": True},
    {"target_confirmed": "false"}, {"collection_status": "odrzucony"},
    {"features_status": "skipped"}, {"target_total_pln": "0.001"},
])
def test_invalid_rows_are_not_silently_coerced(tmp_path, metadata, judgment_payload, changes):
    """Reject wrong identity/scalar/status types and unexplained skips at publication.

    args:
        tmp_path: Isolated workspace root.
        metadata: Artifact provenance fixture.
        judgment_payload: Complete source fixture.
        changes: Invalid field overrides.
    returns:
        None.
    """
    row = {**source_row(judgment_payload), **changes}
    with pytest.raises(ValueError):
        write_cases([row], str(tmp_path / "invalid"), metadata)
    assert not (tmp_path / "invalid/reference.json").exists()
