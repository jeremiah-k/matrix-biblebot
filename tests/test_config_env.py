# ruff: noqa: S105
import tempfile
from pathlib import Path

from biblebot import bot as botmod


def test_load_config_validation_missing_keys(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("matrix_homeserver: https://example.org\n")  # missing others
    assert botmod.load_config(str(cfg)) is None


def test_load_config_ok_and_normalization(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
matrix_room_ids:
  - "!abc:example.org"
        """.strip()
    )
    conf = botmod.load_config(str(cfg))
    assert conf is not None
    assert conf["matrix_room_ids"] == ["!abc:example.org"]


def test_load_environment_prefers_config_dir_env(tmp_path: Path, monkeypatch):
    # Clear all environment variables to ensure clean test
    monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ESV_API_KEY", raising=False)

    cfg = tmp_path / "config.yaml"
    cfg.write_text("matrix_room_ids:\n" '  - "!ignored:example.org"\n')

    # Put a .env in same dir
    envp = tmp_path / ".env"
    envp.write_text("MATRIX_ACCESS_TOKEN=from_config_dir\n")

    # Also set CWD .env which should be ignored if config dir env exists
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.chdir(d)
        Path(".env").write_text("MATRIX_ACCESS_TOKEN=from_cwd\n")
        # Load config first, then pass to load_environment
        config = botmod.load_config(str(cfg))
        token, _ = botmod.load_environment(config, str(cfg))
        assert token == "from_config_dir"
