"""Target admission and multiple-recipient arithmetic without model downloads."""

import asyncio

from dataset.extraction import basal_filtering as basal
from dataset.extraction.model import configuration as config_module
from dataset.extraction.targets import amounts
from dataset.extraction.model import decisions


def test_prior_payment_feature_is_resolved_for_debug_case_without_target(monkeypatch):
    """
    Retain a prior-payment feature even when debug preserves a case without an award.

    args:
        monkeypatch: Scoped target and feature resolvers.

    returns:
        None.
    """

    async def extract_award(*args):
        """
        Supply an excluded earlier payment without any eligible judgment.

        args:
            args: Unused extraction arguments.

        returns:
            Unconfirmed target and embedding diagnostics.
        """
        return {
            "confirmed": False,
            "target_matches": {
                "judgment": None,
                "prior_payment": {"text": "Wypłacono 700 zł."},
            },
        }

    async def prior_payment(server, match, config):
        """
        Resolve the selected feature without modifying the target result.

        args:
            server: Unused inference server.
            match: Earlier-payment source sentence.
            config: Effective pipeline configuration.

        returns:
            Integer feature value.
        """
        assert match["text"] == "Wypłacono 700 zł."
        return 700

    async def ask(*args):
        """Provide an instance result without inference.

        args:
            args: Inference arguments.

        returns:
            Deliberately unknown instance.
        """
        return {"instancja": {"choice": "nieustalona", "confidence": 0.9}}

    async def features(*args):
        """Run primary damage extraction even with an unresolved debug target.

        args:
            args: Extraction arguments.

        returns:
            Source-backed primary damage evidence.
        """
        return {"features": {"damage": "Powód doznał urazu."}, "fields_evaluated": True}

    monkeypatch.setattr(decisions, "ask", ask)
    monkeypatch.setattr(basal, "extract_features", features)
    monkeypatch.setattr(amounts, "extract_award", extract_award)
    monkeypatch.setattr(amounts, "extract_prior_payment", prior_payment)
    result = asyncio.run(
        basal.extract(
            None,
            "Wypłacono 700 zł.",
            config_module.load_config(overrides={"debug": True}),
            42,
        )
    )
    assert result["prior_payment"] == 700
    assert result["fields_evaluated"] is True
    assert "prior_payment" not in result["award"]
    assert result["award"]["confirmed"] is False
