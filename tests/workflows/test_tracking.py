"""Fixture-only local ZenML tracking without application pipeline execution."""

import os
from pathlib import Path
import subprocess
import sys


def test_local_sqlite_run_survives_client_restart(tmp_path):
    """Find a fixture run from another process using the same isolated store.

    args:
        tmp_path: Isolated repository, artifact store and SQLite configuration.

    returns:
        None.
    """
    repository = tmp_path / "repository"
    repository.mkdir()
    environment = {**os.environ, "ZENML_CONFIG_PATH": str(tmp_path / "zenml-config")}
    executable = Path(sys.executable).with_name("zenml")
    subprocess.run(
        [str(executable), "init", "--path", str(repository)],
        env=environment, check=True, capture_output=True, text=True,
    )
    script = repository / "fixture.py"
    script.write_text('''"""Fixture-only local history verification."""
from zenml import pipeline, step

@step
def fixture_value() -> int:
    """Produce a constant with no judgment input.

    args:
        None.
    returns:
        Fixture integer.
    """
    return 7

@pipeline
def fixture_history():
    """Record one fixture-only run.

    args:
        None.
    returns:
        None.
    """
    fixture_value()

print("RUN_ID:", fixture_history().id)
''', encoding="utf-8")
    first = subprocess.run(
        [sys.executable, str(script)], cwd=repository,
        env=environment, check=True, capture_output=True, text=True,
    )
    identifier = first.stdout.split("RUN_ID: ")[-1].splitlines()[0]
    second = subprocess.run(
        [sys.executable, "-c", "from zenml.client import Client; "
         "print(Client().get_pipeline_run('" + identifier + "').id)"],
        cwd=repository, env=environment, check=True, capture_output=True, text=True,
    )
    assert str(identifier) in second.stdout
    assert (tmp_path / "zenml-config" / "local_stores" / "default_zen_store" / "zenml.db").is_file()
