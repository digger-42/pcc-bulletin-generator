import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pcc_bulletin.config import Config


def test_from_env_all_vars_set():
    env = {
        "ANTHROPIC_API_KEY": "sk-test-key",
        "PCC_BULLETIN_FOLDER": "/some/folder",
        "PCC_SERMON_NOTES_ROOT": "/some/notes",
        "PCC_MODEL": "claude-test-model",
    }
    with patch.dict(os.environ, env):
        cfg = Config.from_env()

    assert cfg.api_key == "sk-test-key"
    assert cfg.bulletin_folder == Path("/some/folder")
    assert cfg.sermon_notes_root == Path("/some/notes")
    assert cfg.model == "claude-test-model"


def test_from_env_uses_defaults():
    clean = {"ANTHROPIC_API_KEY": "sk-test"}
    # Remove optional vars so defaults kick in
    for key in ("PCC_BULLETIN_FOLDER", "PCC_SERMON_NOTES_ROOT", "PCC_MODEL"):
        clean.setdefault(key, "")
    with patch.dict(os.environ, {}, clear=True):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            cfg = Config.from_env()

    assert cfg.bulletin_folder == Path("/home/dan/Documents/PCC Bulletins")
    assert cfg.sermon_notes_root == Path("/MaresLeg/Church/SermonNotes")
    assert cfg.model == "claude-sonnet-4-6"


def test_from_env_missing_api_key_raises():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            Config.from_env()


def test_dataclass_fields():
    cfg = Config(
        api_key="k",
        bulletin_folder=Path("/b"),
        sermon_notes_root=Path("/n"),
        model="m",
    )
    assert cfg.api_key == "k"
    assert cfg.bulletin_folder == Path("/b")
    assert cfg.sermon_notes_root == Path("/n")
    assert cfg.model == "m"
