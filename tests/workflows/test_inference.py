"""Basic offline check of the local inference adapter."""

import asyncio
from types import SimpleNamespace

from saos_dataset.extraction.model.configuration import load_config
from saos_workflows.inference import InferenceIdentity, open_local_inference


def test_local_inference_uses_pinned_identity_and_closes_worker(tmp_path):
    """Pass one request through an injected worker without loading weights.

    args:
        tmp_path: External fixture cache directory.
    returns:
        None.
    """
    model = load_config()["system_one"]
    events = []
    request = {"state": "source", "questions": {"fact": {"type": "bool"}}}
    response = {"answers": {"fact": {"noul": 0.8, "probabilities": {"true": 0.8, "false": 0.2}}}}

    def loader(settings, cache):
        """Replace a model download with a fixture path.

        args:
            settings: Effective model settings.
            cache: Selected cache directory.
        returns:
            Fixture snapshot location.
        """
        assert settings == model and cache == tmp_path
        return "snapshot"

    async def worker():
        """Remain active until the inference context closes.

        args:
            None.
        returns:
            None.
        """
        try:
            await asyncio.Event().wait()
        finally:
            events.append("closed")

    async def serve(received):
        """Return one valid answer to the original request.

        args:
            received: Request forwarded by the adapter.
        returns:
            Valid response envelope.
        """
        assert received == request
        return response

    def factory(settings, path):
        """Provide a fixture server for the pinned snapshot.

        args:
            settings: Effective model settings.
            path: Loaded fixture snapshot location.
        returns:
            Server with worker and serve methods.
        """
        assert settings == model and path == "snapshot"
        return SimpleNamespace(worker=worker, serve=serve)

    async def run():
        """Exercise the adapter inside its worker lifetime.

        args:
            None.
        returns:
            None.
        """
        async with open_local_inference(model, tmp_path, model_loader=loader, server_factory=factory) as adapter:
            assert adapter.identity == InferenceIdentity(model["model"], model["revision"])
            await asyncio.sleep(0)
            assert await adapter.serve(request) is response

    asyncio.run(run())
    assert events == ["closed"]
