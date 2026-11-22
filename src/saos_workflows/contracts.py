"""Versioned, non-predictor source/evidence contracts for plain judgment Parquet."""

import hashlib
import json
import math
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal

import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1
MONEY_TYPE = pa.decimal128(38, 2)
TEXT_FIELDS = ("cause", "damage", "limitations")
TABULAR_FIELDS = (
    "judgment_year", "injured_party_count", "prior_payment", "court_type",
    "instance", "court_locality_size", "court_seat",
)
STAGES = ("collection", "targets", "features")
STATUSES = ("pending", "accepted", "rejected", "skipped")
MISSING = (None, "not_available", "brak informacji")


class ContractModel(BaseModel):
    """Reject undeclared fields rather than silently discarding context."""

    model_config = ConfigDict(extra="forbid")


class Span(ContractModel):
    """Half-open Python-character offsets into the normalized judgment text."""

    text: str
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def check_offsets(self):
        """Reject offsets inconsistent with their evidence length.

        args:
            self: Parsed evidence span.
        returns:
            Validated span.
        """
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("Evidence offsets must describe its exact text")
        return self


class TargetAward(Span):
    """One amount window and its complete clause, without inference traces."""

    amount_start: int | None = None
    amount_end: int | None = None
    sentence: Span | None = None
    classes: list[str] | None = None
    operative: bool | None = None
    first_amount: bool | None = None
    procedural: bool | None = None
    similarity: float | None = Field(default=None, ge=-1, le=1)
    pattern: str | None = None
    core_keys: list[str] = Field(default_factory=list)

    @classmethod
    def from_core(cls, value):
        """Adapt an existing matcher window while retaining optional-key presence.

        args:
            cls: Requested window class.
            value: Existing core dictionary.
        returns:
            Typed window with reconstructible core keys.
        """
        return cls(**{**value, "core_keys": list(value)})

    def to_core(self):
        """Restore the core dictionary, including its tuple of eligible classes.

        args:
            self: Serialized window.
        returns:
            Core-compatible matcher window.
        """
        result = self.model_dump(include=set(self.core_keys))
        if "classes" in result and result["classes"] is not None:
            result["classes"] = tuple(result["classes"])
        return result

    @model_validator(mode="after")
    def check_amount(self):
        """Validate nested clause and amount associations.

        args:
            self: Parsed target window.
        returns:
            Validated target window.
        """
        if (self.amount_start is None) != (self.amount_end is None):
            raise ValueError("Amount offsets must be supplied together")
        if self.amount_start is not None and not (
            self.start <= self.amount_start < self.amount_end <= self.end
        ):
            raise ValueError("Amount offsets lie outside their target window")
        if self.sentence is not None and not (
            self.sentence.start <= self.start < self.end <= self.sentence.end
            and self.sentence.text[self.start - self.sentence.start:self.end - self.sentence.start] == self.text
        ):
            raise ValueError("Target window does not match its complete clause")
        return self


class TargetMatch(TargetAward):
    """Selected role match, optionally containing separately supported principals."""

    awards: list[TargetAward] | None = None

    @classmethod
    def from_core(cls, value):
        """Adapt a selected match and all its principal anchors.

        args:
            cls: Requested match class.
            value: Core selected-match dictionary.
        returns:
            Typed match retaining all source windows.
        """
        fields = {**value, "core_keys": list(value)}
        if value.get("awards") is not None:
            fields["awards"] = [TargetAward.from_core(row) for row in value["awards"]]
        return cls(**fields)

    def to_core(self):
        """Restore selected and aggregated core match dictionaries.

        args:
            self: Typed selected match.
        returns:
            Core-compatible dictionary.
        """
        result = super().to_core()
        if "awards" in result and self.awards is not None:
            result["awards"] = [row.to_core() for row in self.awards]
        return result


TARGET_ROLES = (
    "judgment", "request", "judgment-denial", "prior_payment",
    "procedural_costs", "mixed", "other_payments",
)


class TargetContext(ContractModel):
    """The current core award handoff; money lexemes remain lossless strings."""

    suma: str | None = None
    confirmed: bool | None = None
    request: str | None = None
    injured_party_count: int | None = None
    count_missing: str | None = None
    beneficiaries: list[str] | None = None
    status: str | None = None
    excluded: bool | None = None
    denied: bool | None = None
    target_matches: dict[str, TargetMatch | None] | None = None
    excluded_reason: str | None = None
    core_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def restore_arrow_maps(cls, value):
        """Accept Arrow's list-of-pairs representation of nested maps.

        args:
            cls: Target context class.
            value: Model input or one Arrow-decoded context struct.
        returns:
            Input with the typed role map restored to a dictionary.
        """
        if isinstance(value, dict) and isinstance(value.get("target_matches"), list):
            return {**value, "target_matches": dict(value["target_matches"])}
        return value

    @classmethod
    def from_core(cls, value):
        """Freeze an award without changing the dictionary expected by predictors.

        args:
            cls: Requested context class.
            value: Existing extract_targets result.
        returns:
            Typed, Parquet-serializable target context.
        """
        fields = {**value, "core_keys": list(value)}
        count = value.get("injured_party_count")
        if isinstance(count, str):
            if count not in MISSING:
                raise ValueError("Invalid missing recipient count")
            fields.update(injured_party_count=None, count_missing=count)
        matches = value.get("target_matches")
        if matches is not None:
            if set(matches) - {*TARGET_ROLES, "excluded_reason"}:
                raise ValueError("Unknown target-match role")
            fields["excluded_reason"] = matches.get("excluded_reason")
            fields["target_matches"] = {
                key: TargetMatch.from_core(row) if row is not None else None
                for key, row in matches.items() if key != "excluded_reason"
            }
            if "excluded_reason" in matches:
                fields["core_keys"].append("matches_excluded_reason")
        return cls(**fields)

    def to_core(self):
        """Restore the legacy target handoff without rerunning target inference.

        args:
            self: Stored target context.
        returns:
            Existing award dictionary with missing keys and count defaults intact.
        """
        result = self.model_dump(include=set(self.core_keys))
        if "injured_party_count" in result and self.count_missing is not None:
            result["injured_party_count"] = self.count_missing
        if self.target_matches is not None:
            result["target_matches"] = {
                key: row.to_core() if row is not None else None
                for key, row in self.target_matches.items()
            }
            if "matches_excluded_reason" in self.core_keys:
                result["target_matches"]["excluded_reason"] = self.excluded_reason
        return result


class ReviewAnswer(ContractModel):
    """Actual model answer, named by its original Polish question identifier."""

    question: str
    choice: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    noul: float | None = Field(default=None, ge=0, le=1)
    probabilities: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def restore_probabilities(cls, value):
        """Restore probability maps decoded from Arrow without dropping options.

        args:
            cls: Review answer class.
            value: Input answer struct.
        returns:
            Answer with a dictionary probability distribution.
        """
        if isinstance(value, dict) and isinstance(value.get("probabilities"), list):
            return {**value, "probabilities": dict(value["probabilities"])}
        return value


class Review(Span):
    """One reviewed span with unaveraged factuality/leakage/relevance answers."""

    answers: list[ReviewAnswer]
    accepted: bool
    rejection_reasons: list[str] = Field(default_factory=list)

    @classmethod
    def from_core(cls, value):
        """Associate all original question answers with their reviewed source span.

        args:
            cls: Requested review class.
            value: Existing description_reviews entry.
        returns:
            Typed review retaining individual model scores.
        """
        return cls(**{
            **value,
            "answers": [{"question": key, **answer} for key, answer in value["answers"].items()],
        })


class ArtifactMetadata(ContractModel):
    """Artifact-level provenance, never repeated in rows or predictors.

    Queries use the collection phrase_match rule, deduplicated by SAOS ID.
    The optional cap counts unique complete retrieved records, including local
    selection rejections; downstream stages conserve those IDs. HTTP/detail
    failures are run failures, never manufactured rejected rows.
    """

    schema_version: Literal[1] = SCHEMA_VERSION
    stage: Literal["collection", "targets", "features"]
    queries: list[str]
    date_from: date
    date_to: date
    record_limit: int | None = Field(default=None, gt=0)
    phrase_match: Literal["any", "all"] = "any"
    config_hashes: dict[str, str]
    source_identity: str
    model_identities: dict[str, str] = Field(default_factory=dict)
    input_artifact_id: str | None = None
    retrieved_at: str | None = None
    stop_reason: str | None = None
    text_fields: list[str] = list(TEXT_FIELDS)

    @model_validator(mode="after")
    def check_bounds(self):
        """Validate date bounds and collision-free predictor names.

        args:
            self: Artifact-level metadata.
        returns:
            Validated metadata.
        """
        if self.date_from > self.date_to:
            raise ValueError("Artifact date bounds are reversed")
        reserved = set(case_schema().names) - set(TEXT_FIELDS)
        if len(set(self.text_fields)) != len(self.text_fields) or any(
            not name.isidentifier() or not name.isascii() or name in reserved
            or name.endswith(("_evidence", "_reviews", "_status", "_confidence"))
            for name in self.text_fields
        ):
            raise ValueError("Invalid or colliding text feature names")
        return self


def money(value):
    """Accept exact nonnegative PLN representable as decimal128(38, 2).

    args:
        value: Decimal, integer, numeric string or legacy missing marker; never float.
    returns:
        Exact Decimal or None; fractional grosz and overflow raise ValueError.
    """
    if value in MISSING:
        return None
    if isinstance(value, (float, bool)):
        raise ValueError("Money requires Decimal, integer or string, never float/bool")
    try:
        amount = Decimal(value)
        with localcontext() as context:
            context.prec = 40
            fixed = amount.quantize(Decimal("0.01"))
        if not amount.is_finite() or amount < 0 or fixed != amount or amount >= Decimal(10) ** 36:
            raise ValueError("Money is not representable as decimal128(38, 2)")
    except (InvalidOperation, TypeError, OverflowError) as error:
        raise ValueError("Invalid exact PLN amount") from error
    return fixed


def _struct(model):
    """Build the explicit nested Arrow types used by evidence and target handoffs.

    args:
        model: One supported contract model class.
    returns:
        Arrow struct type; no inferred null/list types.
    """
    span = [("text", pa.string()), ("start", pa.int64()), ("end", pa.int64())]
    award = span + [
        ("amount_start", pa.int64()), ("amount_end", pa.int64()),
        ("sentence", pa.struct(span)), ("classes", pa.list_(pa.string())),
        ("operative", pa.bool_()), ("first_amount", pa.bool_()), ("procedural", pa.bool_()),
        ("similarity", pa.float64()), ("pattern", pa.string()),
        ("core_keys", pa.list_(pa.string())),
    ]
    if model is Span:
        return pa.struct(span)
    if model is TargetAward:
        return pa.struct(award)
    if model is TargetMatch:
        return pa.struct(award + [("awards", pa.list_(pa.struct(award)))])
    if model is Review:
        return pa.struct(span + [
            ("answers", pa.list_(pa.struct([
                ("question", pa.string()), ("choice", pa.string()),
                ("confidence", pa.float64()), ("noul", pa.float64()),
                ("probabilities", pa.map_(pa.string(), pa.float64())),
            ]))),
            ("accepted", pa.bool_()), ("rejection_reasons", pa.list_(pa.string())),
        ])
    raise ValueError("Unsupported nested contract")


def case_schema(text_fields=TEXT_FIELDS):
    """Declare the frozen typed row schema, with configured text columns.

    args:
        text_fields: Ordered original text predictor names.
    returns:
        Versioned Arrow schema; artifact provenance is stored separately once.
    """
    context = pa.struct([
        ("suma", pa.string()), ("confirmed", pa.bool_()), ("request", pa.string()),
        ("injured_party_count", pa.int64()), ("count_missing", pa.string()),
        ("beneficiaries", pa.list_(pa.string())), ("status", pa.string()),
        ("excluded", pa.bool_()), ("denied", pa.bool_()),
        ("target_matches", pa.map_(pa.string(), _struct(TargetMatch))),
        ("excluded_reason", pa.string()), ("core_keys", pa.list_(pa.string())),
    ])
    fields = [
        pa.field("saos_id", pa.int64(), nullable=False),
        pa.field("source_json", pa.large_string(), nullable=False),
        pa.field("judgment_text", pa.large_string()),
        pa.field("text_sha256", pa.string()),
        pa.field("matched_phrases", pa.list_(pa.string()), nullable=False),
        pa.field("source_uri", pa.string()),
        pa.field("judgment_date", pa.date32()),
        pa.field("source_court_type", pa.string()),
        pa.field("judgment_type", pa.string()),
        pa.field("court_id", pa.int64()), pa.field("court_name", pa.string()),
        pa.field("division_id", pa.int64()), pa.field("division_name", pa.string()),
        pa.field("case_numbers", pa.list_(pa.string())),
        pa.field("target_total_pln", MONEY_TYPE), pa.field("target_confirmed", pa.bool_()),
        pa.field("target_context", context), pa.field("eligible", pa.bool_()),
        pa.field("rejection_reasons", pa.list_(pa.string()), nullable=False),
    ]
    fields += [pa.field(f"{stage}_status", pa.string(), nullable=False) for stage in STAGES]
    for name in (*text_fields, *TABULAR_FIELDS):
        dtype = pa.int64() if name in {"judgment_year", "injured_party_count", "prior_payment"} else pa.string()
        fields += [
            pa.field(name, dtype), pa.field(f"{name}_evidence", pa.list_(_struct(Span))),
            pa.field(f"{name}_reviews", pa.list_(_struct(Review))),
            pa.field(f"{name}_status", pa.string()), pa.field(f"{name}_confidence", pa.float64()),
        ]
    return pa.schema(fields, metadata={b"saos_schema_version": str(SCHEMA_VERSION).encode()})


def source_row(source, *, judgment_text=None, matched_phrases=(), source_uri=None, text_fields=TEXT_FIELDS):
    """Create an unprocessed row retaining the complete judgment-detail envelope.

    args:
        source: Complete SAOS detail response, including unknown outer/data fields.
        judgment_text: Optional normalized text; raw HTML remains in source_json.
        matched_phrases: Row-specific union of matching configured phrases.
        source_uri: Original judgment-detail endpoint or provenance URI.
        text_fields: Configured text predictor column names.
    returns:
        Complete nullable row with pending downstream states, not an approved sample.
    """
    identifier = source.get("data", {}).get("id")
    if type(identifier) is not int or not 0 < identifier < 2**63:
        raise ValueError("SAOS ID must be a positive signed 64-bit integer")
    data = source["data"]
    division = data.get("division") or {}
    court = division.get("court") or {}
    row = dict.fromkeys(case_schema(text_fields).names)
    row.update(
        saos_id=identifier, source_json=json.dumps(source, ensure_ascii=False, allow_nan=False),
        judgment_text=judgment_text,
        text_sha256=hashlib.sha256(judgment_text.encode()).hexdigest() if judgment_text is not None else None,
        matched_phrases=list(dict.fromkeys(matched_phrases)), source_uri=source_uri,
        judgment_date=date.fromisoformat(data["judgmentDate"]) if data.get("judgmentDate") else None,
        source_court_type=data.get("courtType"), judgment_type=data.get("judgmentType"),
        court_id=court.get("id"), court_name=court.get("name"),
        division_id=division.get("id"), division_name=division.get("name"),
        case_numbers=[case["caseNumber"] for case in data.get("courtCases", [])],
        rejection_reasons=[], **{f"{stage}_status": "pending" for stage in STAGES},
    )
    return row


def predictor_fields(metadata):
    """Expose only original predictor names, never sources, labels or evidence.

    args:
        metadata: Artifact metadata containing configured text feature names.
    returns:
        Explicit predictor allowlist; downstream training still chooses its inputs.
    """
    return (*metadata.text_fields, *TABULAR_FIELDS)


def validate_row(row, metadata):
    """Validate one retained case and normalize legacy missing predictors.

    args:
        row: Complete row mapping; rejected/skipped rows are not discarded.
        metadata: Artifact contract defining configured text columns.
    returns:
        Arrow-ready row with exact money and typed nested evidence.
    """
    schema = case_schema(metadata.text_fields)
    if set(row) != set(schema.names):
        raise ValueError("Case columns do not match the artifact schema")
    result = dict(row)
    identifier = result["saos_id"]
    if type(identifier) is not int or not 0 < identifier < 2**63:
        raise ValueError("SAOS ID must be a positive signed 64-bit integer")
    source = json.loads(result["source_json"])
    if not isinstance(source, dict) or not isinstance(source.get("data"), dict) or (
        type(source["data"].get("id")) is not int or source["data"]["id"] != identifier
    ):
        raise ValueError("Source envelope ID differs from saos_id")
    for stage in STAGES:
        if result[f"{stage}_status"] not in STATUSES:
            raise ValueError("Unknown stage status")
    if result["matched_phrases"] is None or result["rejection_reasons"] is None:
        raise ValueError("Matched phrases and rejection reasons must be lists")
    if any(result[f"{stage}_status"] in {"rejected", "skipped"} for stage in STAGES) and not result["rejection_reasons"]:
        raise ValueError("Rejected/skipped cases require an explicit reason")
    result["target_total_pln"] = money(result["target_total_pln"])
    if result["target_confirmed"] is True and result["target_total_pln"] is None:
        raise ValueError("Confirmed target requires an exact amount, including zero")
    if result["eligible"] is True and (
        result["target_confirmed"] is not True or result["features_status"] != "accepted"
        or any(result[f"{stage}_status"] != "accepted" for stage in STAGES)
        or result["rejection_reasons"]
    ):
        raise ValueError("Eligibility requires target confirmation and all admission stages")
    if metadata.stage == "features" and type(result["eligible"]) is not bool:
        raise ValueError("Final feature artifacts require an explicit eligibility flag")
    text = result["judgment_text"]
    if text is not None and result["text_sha256"] != hashlib.sha256(text.encode()).hexdigest():
        raise ValueError("Normalized judgment text hash differs")
    for name in predictor_fields(metadata):
        if result[name] in MISSING:
            result[name] = None
        for suffix, model in (("evidence", Span), ("reviews", Review)):
            key = f"{name}_{suffix}"
            if result[key] is not None:
                parsed = [item if isinstance(item, model) else model.model_validate(item) for item in result[key]]
                if any(text is None or text[item.start:item.end] != item.text for item in parsed):
                    raise ValueError("Feature evidence/review does not match normalized source")
                result[key] = [item.model_dump() for item in parsed]
    context = result["target_context"]
    if context is not None:
        context = context if isinstance(context, TargetContext) else TargetContext.model_validate(context)
        if context.confirmed != result["target_confirmed"] or money(context.suma) != result["target_total_pln"]:
            raise ValueError("Target context differs from target columns")
        for match in (context.target_matches or {}).values():
            if match is None:
                continue
            for window in [match, *(match.awards or [])]:
                for span in [window, *([window.sentence] if window.sentence is not None else [])]:
                    if text is None or text[span.start:span.end] != span.text:
                        raise ValueError("Target evidence does not match normalized source")
        result["target_context"] = context.model_dump()
    for column in schema:
        value = result[column.name]
        if value is None:
            if not column.nullable:
                raise ValueError(f"Required case column is null: {column.name}")
            continue
        if pa.types.is_int64(column.type) and (type(value) is not int or not -2**63 <= value < 2**63):
            raise ValueError(f"Case column requires an exact int64: {column.name}")
        if pa.types.is_boolean(column.type) and type(value) is not bool:
            raise ValueError(f"Case column requires a boolean: {column.name}")
        if (pa.types.is_string(column.type) or pa.types.is_large_string(column.type)) and not isinstance(value, str):
            raise ValueError(f"Case column requires a string: {column.name}")
        if pa.types.is_float64(column.type) and (
            type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
        ):
            raise ValueError(f"Case confidence requires a finite probability: {column.name}")
    return result
