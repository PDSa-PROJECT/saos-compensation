"""Dataset admission boundaries without model inference."""

import asyncio

import pytest

from dataset.extraction import basal_filtering as basal
from dataset.extraction.model import configuration as config_module
from dataset.extraction.model import decisions
from dataset.extraction.targets import amounts


@pytest.mark.parametrize(
    ("confirmed", "debug", "probability"),
    [
        (False, False, 0.9),
        (True, False, 0.9),
        (False, False, 0.4),
        (False, True, 0.4),
        (False, True, 0.9),
    ],
)
def test_target_does_not_prevent_feature_inference(
    monkeypatch,
    confirmed,
    debug,
    probability,
):
    """
    Extract predictors after target selection even when the target is unresolved.

    args:
        monkeypatch: Scoped function replacements.
        confirmed: Whether the extracted target meets admission rules.
        debug: Whether low-confidence proposals may be retained.
        probability: Award verification probability.

    returns:
        None.
    """
    events = []
    award = amounts.finish_award(
        {"suma": "100"},
        confirmed,
        {"noul": probability},
    )

    async def extract_award(server, text, diagnostics, config):
        """
        Supply a target without invoking the model.

        args:
            server: Unused inference server.
            text: Source judgment.
            diagnostics: Unused fragment diagnostics.
            config: Effective configuration.

        returns:
            Controlled award decision.
        """
        events.append("target")
        return award

    async def ask(server, state, questions, config):
        """
        Check that instance inference follows target selection.

        args:
            server: Unused inference server.
            state: Model input.
            questions: Requested model decisions.
            config: Effective configuration.

        returns:
            Instance decision.
        """
        assert events == ["target"]
        assert set(questions) == {"instancja"}
        events.append("instance")
        return {"instancja": {"choice": "nieustalona", "confidence": 0.9}}

    async def features(*args):
        """Record feature extraction after target selection.

        args:
            args: Feature extraction arguments.

        returns:
            Damage feature and evaluation flag.
        """
        events.append("features")
        return {"features": {"damage": "Source damage."}, "fields_evaluated": True}

    monkeypatch.setattr(basal, "extract_features", features)
    monkeypatch.setattr(amounts, "extract_award", extract_award)
    monkeypatch.setattr(decisions, "ask", ask)
    config = config_module.load_config()
    config["api"]["debug"] = debug
    result = asyncio.run(basal.extract(None, "Source judgment.", config, 42))
    assert result["award"] == award
    assert events == ["target", "instance", "features"]
    assert result["fields_evaluated"] is True
