import os
import tempfile
from pathlib import Path

import pytest

from biblebot import bot as botmod


def test_load_config_validation_missing_keys(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("matrix_homeserver: https://example.org\n")  # missing others
    assert botmod.load_config(str(cfg)) is None


def test_load_config_ok_and_normalization(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
matrix_homeserver: https://example.org/
matrix_user: "@bot:example.org"
matrix_room_ids:
  - "!abc:example.org"
        """.strip()
    )
    conf = botmod.load_config(str(cfg))
    assert conf is not None
    assert conf["matrix_homeserver"] == "https://example.org"


def test_load_environment_prefers_config_dir_env(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("matrix_homeserver: https://example.org\n")

    # Put a .env in same dir
    envp = tmp_path / ".env"
    envp.write_text("MATRIX_ACCESS_TOKEN=from_config_dir\n")

    # Also set CWD .env which should be ignored if config dir env exists
    cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            Path(".env").write_text("MATRIX_ACCESS_TOKEN=from_cwd\n")

            token, _ = botmod.load_environment(str(cfg))
            assert token == "from_config_dir"
    finally:
        os.chdir(cwd)
