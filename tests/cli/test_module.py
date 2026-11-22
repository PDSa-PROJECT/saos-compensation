"""Module entry points for both independent stages."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("module,flag", [("saos_dataset.cli", "--download-path"), ("saos_dataset.cli.process", "--input-path")])
def test_module_help(tmp_path, module, flag):
    """Run each CLI module outside the checkout without source-path modifications.

    args:
        tmp_path: Independent working directory.
        module: Stage-specific module.
        flag: Expected stage-specific option.

    returns:
        None.
    """
    result = subprocess.run([sys.executable, "-m", module, "--help"], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert flag in result.stdout and "--no-debug" in result.stdout
