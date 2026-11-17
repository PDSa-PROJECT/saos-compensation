"""Coordinate target, prior-payment, instance and feature extraction."""

import hashlib

from .targets import amounts
from .model import decisions
from .source import text as api
from .features import extract_features


async def extract(server, text, config, identifier):
    """
    Extract source-grounded factual descriptions and separate monetary targets.

    args:
        server: Local inference server.
        text: Normalized Polish source text.
        config: Effective pipeline or acquisition settings.
        identifier: Stable judgment identifier.

    returns:
        Feature and target results for independent admission checks.
    """
    print(f"ID {identifier}: extracting target", flush=True)
    award = await amounts.extract_award(server, text, [], config)
    prior_features = {}
    if "prior_payment" in config["metadata_fields"]:
        prior_features["prior_payment"] = await amounts.extract_prior_payment(
            server, award.get("target_matches", {}).get("prior_payment"), config
        )
    threshold = config["system_one"]["minimum_probability"]
    heading = api.REASONS.search(text)
    header = text[: min(heading.start() if heading else len(text), 4000)]
    instance = await decisions.ask(
        server,
        header,
        {"instancja": {"type": "choice", **config["questions"]["instance"]}},
        config,
    )
    instance = instance["instancja"]
    features = await extract_features(server, text, config, identifier)
    return {
        "id": identifier,
        "award": award,
        **prior_features,
        **features,
        "instance": {
            "value": instance["choice"]
            if instance["choice"] != "nieustalona"
            and instance["confidence"] >= threshold
            else "brak informacji",
            "decision": instance,
            "source": header,
            "status": "review required",
        },
        "status": "candidates for review; not approved for training",
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
