"""Reject evidence references even when semantic review assigns high scores."""

import pytest

from saos_dataset.extraction.features import select_facts
from saos_dataset.extraction.source.text import EVIDENCE_MARKER


@pytest.mark.parametrize("text", [
    "Bezsporne.", "Okoliczność bezsporna.",
    "Dowód: przesłuchanie powódki K. Z. (1)", "Dowody: dokumentacja medyczna, k. 42.",
])
def test_evidence_marker_cannot_become_a_feature(text):
    """Keep source references out of predictors despite high model confidence.

    args:
        text: Non-descriptive source evidence reference.

    returns:
        None.
    """
    row = {"text": text, "answers": {"sekcja": {"choice": "fakty", "confidence": 0.99}, "wyciek": {"noul": 0.01}}}
    assert select_facts([row], 0.6, 0.4) == []
    assert "evidence marker" in row["rejection_reasons"][0]


def test_factual_statement_is_not_an_evidence_marker():
    """Retain facts containing ordinary descriptions of established circumstances.

    args:
        None.

    returns:
        None.
    """
    assert not EVIDENCE_MARKER.search("Bezsporne było, że powódka utraciła możliwość pracy.")
