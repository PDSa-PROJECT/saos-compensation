"""Offline native inference boundary and worker lifetime checks."""

import asyncio
from types import SimpleNamespace

import pytest

from saos_dataset.extraction.model.configuration import load_config
from saos_workflows.inference import InferenceIdentity, LocalInferenceAdapter, open_local_inference
from saos_workflows.inference import local


@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
def test_local_context_preserves_identity_and_closes_worker(tmp_path, failure):
    """Use injected components without weights and close on all exit paths.

    args:
        tmp_path: Fake external weight cache.
        failure: Optional consumer exception.
    returns:
        None.
    """
    model = load_config()["system_one"]
    events = []
    request = {"state": "source", "questions": {"fact": {"type": "bool"}}, "lang": "pl"}
    response = {"answers": {"fact": {"noul": 0.8, "probabilities": {"true": 0.8, "false": 0.2}}}}

    def loader(settings, cache):
        """Capture the explicit snapshot instead of downloading it.

        args:
            settings: Effective model settings.
            cache: External cache directory.
        returns:
            Fake local snapshot path.
        """
        assert settings == model
        assert cache == tmp_path
        events.append("loaded")
        return "snapshot"

    async def worker():
        """Remain alive until cancellation from the core lifetime context.

        args:
            None.
        returns:
            None.
        """
        events.append("started")
        try:
            await asyncio.Event().wait()
        finally:
            events.append("stopped")

    async def serve(received):
        """Echo a valid response to the unchanged model request.

        args:
            received: Request passed through the adapter.
        returns:
            Valid raw answer envelope.
        """
        assert received == request
        return response

    def factory(settings, path):
        """Construct the test server with no Basal import.

        args:
            settings: Explicit inference settings.
            path: Fake loaded snapshot.
        returns:
            Fake worker and request server.
        """
        assert settings == model
        assert path == "snapshot"
        return SimpleNamespace(worker=worker, serve=serve)

    async def run():
        """Exercise one request and the selected context exit.

        args:
            None.
        returns:
            None.
        """
        async with open_local_inference(model, tmp_path, model_loader=loader, server_factory=factory) as adapter:
            assert adapter.identity == InferenceIdentity(model["model"], model["revision"])
            assert adapter.identity.engine_version == "2.4.1"
            await asyncio.sleep(0)
            assert await adapter.serve(request) is response
            if failure:
                raise failure()

    if failure:
        with pytest.raises(failure):
            asyncio.run(run())
    else:
        asyncio.run(run())
    assert events == ["loaded", "started", "stopped"]


@pytest.mark.parametrize("response", [None, [], {"truncated": True}, {"answers": {}},
    {"answers": {"fact": {"noul": 0.8, "probabilities": {"true": 0.1, "false": 0.9}}}}])
def test_invalid_responses_are_rejected(response):
    """Reject transport envelopes and answers that cannot pass core validation.

    args:
        response: Invalid fake server response.
    returns:
        None.
    """
    async def serve(request):
        """Return the selected malformed response.

        args:
            request: Unused model request.
        returns:
            Invalid response fixture.
        """
        return response

    model = load_config()["system_one"]
    adapter = LocalInferenceAdapter(SimpleNamespace(serve=serve), InferenceIdentity(model["model"], model["revision"]))
    with pytest.raises(ValueError):
        asyncio.run(adapter.serve({"questions": {"fact": {"type": "bool"}}, "state": "text"}))


def test_extraction_offsets_use_core_source_validation():
    """Do not allow source-mismatched extraction through the new adapter.

    args:
        None.
    returns:
        None.
    """
    async def serve(request):
        """Return a value whose offsets describe different input text.

        args:
            request: Existing extraction request.
        returns:
            Unsupported extraction response.
        """
        return {"answers": {"extract": {"data": {"damage": "other"}, "fields": {"damage": {"start": 0, "end": 5, "confidence": 0.9}}}}}

    model = load_config()["system_one"]
    adapter = LocalInferenceAdapter(SimpleNamespace(serve=serve), InferenceIdentity(model["model"], model["revision"]))
    request = {"state": "source", "questions": {"extract": {"type": "extract", "schema": {"properties": {"damage": {}}}}}}
    with pytest.raises(ValueError, match="source span"):
        asyncio.run(adapter.serve(request))


def test_server_failure_is_not_retried():
    """Propagate operational failure rather than returning an empty result.

    args:
        None.
    returns:
        None.
    """
    calls = []

    async def serve(request):
        """Fail the only server invocation.

        args:
            request: Model request.
        returns:
            None; raises an operational failure.
        """
        calls.append(request)
        raise RuntimeError("worker failed")

    model = load_config()["system_one"]
    adapter = LocalInferenceAdapter(SimpleNamespace(serve=serve), InferenceIdentity(model["model"], model["revision"]))
    with pytest.raises(RuntimeError, match="worker failed"):
        asyncio.run(adapter.serve({"state": "source"}))
    assert len(calls) == 1


@pytest.mark.parametrize("change", [{"revision": "main"}, {"revision": "0" * 40}, {"model": "Remek/basal-2.0-max"}])
def test_unpinned_or_unsupported_model_fails_before_loading(tmp_path, change):
    """Keep new local choices within the pinned core-supported snapshots.

    args:
        tmp_path: Unused cache directory.
        change: Invalid model settings override.
    returns:
        None.
    """
    async def run():
        """Enter an invalid model context without reaching a download.

        args:
            None.
        returns:
            None.
        """
        async with open_local_inference({**load_config()["system_one"], **change}, tmp_path):
            pytest.fail("Invalid model reached inference")

    with pytest.raises(ValueError):
        asyncio.run(run())


def test_runtime_identity_is_verified_before_loading(tmp_path, monkeypatch):
    """Reject an installed engine that would be mislabeled as the pinned runtime.

    args:
        tmp_path: Unused cache directory.
        monkeypatch: Runtime version replacement.
    returns:
        None.
    """
    def wrong_version(package):
        """Report a different installed engine without loading a model.

        args:
            package: Distribution requested by the adapter.
        returns:
            Incompatible installed version.
        """
        assert package == "basal"
        return "9.0.0"

    async def run():
        """Attempt to start the production server with the wrong runtime.

        args:
            None.
        returns:
            None.
        """
        async with open_local_inference(load_config()["system_one"], tmp_path):
            pytest.fail("Wrong engine reached inference")

    monkeypatch.setattr(local, "version", wrong_version)
    with pytest.raises(ValueError, match="exactly 2.4.1"):
        asyncio.run(run())
