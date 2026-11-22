"""Installed console entry points independent of the current directory."""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("command,options", [
    ("get-raw-data", ["--max-age-years", "--max-pages", "--max-gib", "--download-path", "--timeout", "--debug", "--no-debug"]),
    ("process-data", ["--input-path", "--output-path", "--max-gib", "--debug", "--no-debug"]),
])
def test_installed_command_help(tmp_path, command, options):
    """Expose each command's own options outside the source checkout.

    args:
        tmp_path: Working directory without source files.
        command: Installed console entry point.
        options: Options expected for this stage.

    returns:
        None.
    """
    result = subprocess.run([str(Path(sys.executable).parent / command), "--help"], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert f"usage: {command}" in result.stdout
    assert all(option in result.stdout for option in options)


def test_raw_cli_imports_no_processing_or_inference_modules():
    """Keep download startup independent of extraction and accelerator packages.

    args:
        None.

    returns:
        None.
    """
    subprocess.run([sys.executable, "-c", "import saos_dataset.cli.main; import sys; assert not any(name in sys.modules for name in ('torch', 'transformers', 'basal', 'saos_dataset.processing.pipeline', 'saos_dataset.extraction'))"], check=True)
