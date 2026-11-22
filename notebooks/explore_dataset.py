import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    """Import the notebook's local exploration dependencies.

    args:
        None.
    returns:
        Libraries and the existing judgment schema.
    """
    import json
    from pathlib import Path

    import marimo as mo
    import polars as pl
    import pyarrow.parquet as pq

    from saos_dataset.storage.parquet import SCHEMA

    return Path, SCHEMA, json, mo, pl, pq


@app.cell
def _(mo):
    """Present the local file and overview controls as one submitted form.

    args:
        mo: marimo UI and display functions.
    returns:
        Apply form for the overview.
    """
    overview = mo.ui.dictionary({
        "path": mo.ui.text(label="Local Parquet path", full_width=True),
        "selection": mo.ui.dropdown(
            ["Any", "selected", "filtered", "rejected"], value="Any", label="Selection"
        ),
        "eligibility": mo.ui.dropdown(
            ["Any", "Eligible", "Ineligible", "Not evaluated"], value="Any", label="Eligibility"
        ),
        "amount": mo.ui.dropdown(
            ["Any", "Missing", "Zero", "Positive"], value="Any", label="Target amount (PLN)"
        ),
        "reason": mo.ui.text(label="Selection reason contains (case-sensitive)"),
    }).form(submit_button_label="Apply")
    mo.vstack([
        mo.md("""
        # Explore judgment data
        Enter the path to one local SAOS Parquet file, set filters, and click
        **Apply**. This notebook only reads saved data; it cannot run a pipeline.
        """),
        overview,
    ])
    return (overview,)


@app.cell
def _(Path, SCHEMA, pl, pq):
    """Define narrow, lazy queries over the shared judgment schema.

    args:
        Path: Local filesystem path type.
        SCHEMA: Shared PyArrow judgment schema.
        pl: Polars query API.
        pq: PyArrow Parquet metadata reader.
    returns:
        File validation and overview query builders.
    """
    def open_dataset(location):
        """Validate one local file's footer and return a lazy scan.

        args:
            location: Explicit path, absolute or relative to the working directory.
        returns:
            Validated path and lazy Parquet scan.
        """
        path = Path(location.strip()).expanduser().absolute()
        if not path.is_file():
            raise ValueError("Enter the path to one existing local Parquet file.")
        if not pq.read_schema(path).equals(SCHEMA, check_metadata=False):
            raise ValueError("Incompatible Parquet schema: expected the SAOS judgment layout.")
        return path, pl.scan_parquet(path, glob=False)

    def overview_queries(dataset, filters):
        """Build summaries and a review sample without projecting large columns.

        args:
            dataset: Validated lazy scan.
            filters: Values from the submitted overview form.
        returns:
            Lazy counts, selection/eligibility breakdown, reasons and sample queries.
        """
        rows = dataset.select(
            "saos_id", "selection_status", "selection_reason", "target_total_pln", "eligible"
        )
        eligible = pl.col("eligible")
        amount = pl.col("target_total_pln")
        if filters["selection"] != "Any":
            rows = rows.filter(pl.col("selection_status") == filters["selection"])
        if filters["eligibility"] != "Any":
            rows = rows.filter({
                "Eligible": eligible.eq(True),
                "Ineligible": eligible.eq(False),
                "Not evaluated": eligible.is_null(),
            }[filters["eligibility"]])
        if filters["amount"] != "Any":
            rows = rows.filter({
                "Missing": amount.is_null(), "Zero": amount.eq(0), "Positive": amount.gt(0),
            }[filters["amount"]])
        if reason := filters["reason"].strip():
            rows = rows.filter(pl.col("selection_reason").str.contains(reason, literal=True))

        counts = rows.select(
            pl.len().alias("judgments"),
            amount.is_null().sum().alias("missing_targets"),
            amount.eq(0).sum().alias("zero_targets"),
        )
        outcomes = (
            rows.group_by("selection_status", "eligible").len(name="judgments")
            .sort(["selection_status", "eligible"]).limit(20)
        )
        reasons = (
            rows.filter(pl.col("selection_reason").is_not_null())
            .group_by("selection_reason").len(name="judgments")
            .sort(["judgments", "selection_reason"], descending=[True, False]).limit(10)
        )
        # Preserve exact decimals and 64-bit IDs when displaying the sample in the browser.
        sample = rows.limit(50).with_columns(amount.cast(pl.String), pl.col("saos_id").cast(pl.String))
        return counts, outcomes, reasons, sample

    return open_dataset, overview_queries


@app.cell
def _(mo, open_dataset, overview, overview_queries, pl):
    """Run the overview only on submitted filter values.

    args:
        mo: marimo UI and display functions.
        open_dataset: Local file validator and lazy scanner.
        overview: Apply form.
        overview_queries: Lazy overview query builder.
        pl: Polars query API.
    returns:
        Lazy scan for follow-up judgment inspection.
    """
    mo.stop(overview.value is None)
    try:
        path, dataset = open_dataset(overview.value["path"])
        counts, outcomes, reasons, sample = pl.collect_all(
            overview_queries(dataset, overview.value), engine="streaming"
        )
    except (OSError, RuntimeError, ValueError, pl.exceptions.PolarsError) as error:
        mo.stop(True, mo.callout(mo.plain_text(str(error)), kind="danger"))

    mo.vstack([
        mo.md("## Filtered overview"),
        mo.plain_text(str(path)),
        mo.ui.table(counts, selection=None),
        mo.md("### Selection and eligibility (unset means not evaluated)"),
        mo.ui.table(outcomes, selection=None),
        mo.md("### Top 10 selection reasons"),
        mo.ui.table(reasons, selection=None),
        mo.md("### First 50 matching judgments (not a random sample)"),
        mo.ui.table(sample, selection=None),
    ])
    return (dataset,)


@app.cell
def _(dataset, mo):
    """Offer a fresh detail form after every successful Apply.

    args:
        dataset: Lazy scan of the applied file.
        mo: marimo UI and display functions.
    returns:
        Run form for the single-judgment lookup.
    """
    mo.stop(dataset is None)
    judgment = mo.ui.text(label="SAOS judgment ID").form(submit_button_label="Run")
    mo.vstack([
        mo.md("## Inspect one judgment\nLookup uses the applied file, independent of overview filters."),
        judgment,
    ])
    return (judgment,)


@app.cell
def _(dataset, json, judgment, mo, pl):
    """Read saved source, target and feature evidence on explicit submission.

    args:
        dataset: Lazy scan of the applied file.
        json: JSON decoder.
        judgment: Run form with the judgment ID.
        mo: marimo UI and display functions.
        pl: Polars query API.
    returns:
        None.
    """
    mo.stop(judgment.value is None)
    try:
        entered_id = judgment.value.strip()
        if not (entered_id.isascii() and entered_id.isdecimal() and 0 < int(entered_id) < 2**63):
            raise ValueError("Enter a positive SAOS judgment ID in the signed 64-bit range.")
        identifier = int(entered_id)
        result = (
            dataset.filter(pl.col("saos_id") == identifier)
            .drop("selected_record_json").limit(1).collect(engine="streaming")
        )
        mo.stop(result.is_empty(), mo.callout(f"Judgment {identifier} is not in the applied file."))
        row = result.row(0, named=True)
        text = row.pop("judgment_text")
        source = json.loads(row.pop("source_json"))
        target_json = row.pop("target_json")
        features_json = row.pop("features_json")
        target = None if target_json is None else json.loads(target_json)
        features = None if features_json is None else json.loads(features_json)
        total = row["target_total_pln"]
        row["target_total_pln"] = None if total is None else str(total)
        row["saos_id"] = str(identifier)
    except (OSError, ValueError, TypeError, pl.exceptions.PolarsError) as error:
        mo.stop(True, mo.callout(mo.plain_text(str(error)), kind="danger"))

    mo.vstack([
        mo.json(row),
        mo.ui.tabs({
            "Judgment text": mo.plain_text(text) if text is not None else mo.md("No normalized text."),
            "SAOS response": mo.json(source),
            "Target": mo.json(target) if target is not None else mo.md("No saved target details."),
            "Features and evidence": mo.vstack([
                mo.md("Saved spans and reviews refer to the same judgment text by `start`/`end` offsets. "
                      "Review answers and scores are shown as stored."),
                mo.json(features),
            ]) if features is not None else mo.md("No saved feature details."),
        }),
    ])


if __name__ == "__main__":
    app.run()
