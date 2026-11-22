"""Processing configuration boundaries and checkpoint compatibility."""

import pytest
import yaml

from saos_dataset.extraction.model import configuration


def test_changed_question_invalidates_checkpoint(
    config_directory,
    output_root,
    monkeypatch,
    tmp_path,
):
    """Resume unchanged settings and reject a changed question on resume.

    args:
        config_directory: Isolated processing YAML directory.
        output_root: Prepared raw input and processing output root.
        monkeypatch: Scoped repository-root replacement.
        tmp_path: Temporary dataset root.

    returns:
        None.
    """
    from saos_dataset.storage import checkpoints
    from saos_dataset.storage.files import write_json

    config = configuration.load_config(config_directory)
    monkeypatch.setattr(checkpoints, "ROOT", tmp_path)
    checkpoint = checkpoints.load_checkpoint(config)
    write_json(
        tmp_path / config["processing"]["output_path"] / "checkpoint.json", checkpoint
    )
    assert checkpoints.load_checkpoint(config) == checkpoint
    path = config_directory / "features.yaml"
    settings = configuration.read_config(path)
    settings["text_fields"]["damage"] = "Co zostało uszkodzone?"
    path.write_text(yaml.safe_dump(settings, allow_unicode=True))
    changed = configuration.load_config(config_directory)
    with pytest.raises(ValueError, match="Extraction settings changed"):
        checkpoints.load_checkpoint(changed)


def test_changed_amount_context_invalidates_processing_checkpoint(config_directory, output_root):
    """Prevent mixing records extracted with different monetary context sizes.

    args:
        config_directory: Isolated processing YAML directory.
        output_root: Prepared raw input and isolated output root.

    returns:
        None.
    """
    from saos_dataset.storage import checkpoints

    config = configuration.load_config(config_directory)
    state = checkpoints.load_checkpoint(config)
    checkpoints.save_checkpoint(output_root / config["processing"]["output_path"], state)
    path = config_directory / "targets.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["embedding"]["context_words_after"] += 1
    path.write_text(yaml.safe_dump(settings, allow_unicode=True))
    with pytest.raises(ValueError, match="Extraction settings changed"):
        checkpoints.load_checkpoint(configuration.load_config(config_directory))
