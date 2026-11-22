from datetime import date

import pytest

from saos_dataset.processing.validation import validate_judgment


@pytest.mark.parametrize("defect", ["id", "date", "court", "case", "text", "type"])
def test_invalid_judgments_are_rejected(judgment_payload, defect):
    """
    Verify invalid judgments are rejected.

    args:
        judgment_payload: Fresh structurally valid SAOS source payload.
        defect: Malformed field under examination.

    returns:
        None.
    """
    payload = judgment_payload
    data = payload["data"]
    if defect == "id":
        data["id"] = True
    elif defect == "date":
        data["judgmentDate"] = "2010-01-01"
    elif defect == "court":
        data["division"]["court"]["id"] = False
    elif defect == "case":
        data["courtCases"] = []
    elif defect == "text":
        data["textContent"] = "<p> </p>"
    else:
        data["judgmentType"] = "REASONS"
    with pytest.raises(ValueError):
        validate_judgment(payload, 254930, date(2016, 10, 29), date(2026, 10, 29))
