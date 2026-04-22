"""Tests for runtime path resolution."""

from pathlib import Path
from unittest.mock import patch

from biblebot import auth, cli, paths


def test_default_paths_use_legacy_config_home():
    """Default path model should remain ~/.config/matrix-biblebot."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("pathlib.Path.home", return_value=Path("/home/testuser")):
            assert paths.get_home_dir() == Path(
                "/home/testuser/.config/matrix-biblebot"
            )
            assert paths.get_config_path() == Path(
                "/home/testuser/.config/matrix-biblebot/config.yaml"
            )
            assert paths.get_credentials_path() == Path(
                "/home/testuser/.config/matrix-biblebot/credentials.json"
            )
            assert paths.get_e2ee_store_dir() == Path(
                "/home/testuser/.config/matrix-biblebot/e2ee-store"
            )


def test_biblebot_home_overrides_all_runtime_paths(tmp_path):
    """BIBLEBOT_HOME should unify config/credentials/store paths."""
    with patch.dict("os.environ", {paths.ENV_BIBLEBOT_HOME: str(tmp_path)}, clear=True):
        assert paths.get_home_dir() == tmp_path
        assert paths.get_config_path() == tmp_path / "config.yaml"
        assert paths.get_credentials_path() == tmp_path / "credentials.json"
        assert paths.get_e2ee_store_dir() == tmp_path / "e2ee-store"


def test_cli_default_config_path_honors_biblebot_home(tmp_path):
    """CLI default config path should follow BIBLEBOT_HOME."""
    with patch.dict("os.environ", {paths.ENV_BIBLEBOT_HOME: str(tmp_path)}, clear=True):
        with patch.object(cli, "CONFIG_DIR", None):
            assert cli.get_default_config_path() == tmp_path / "config.yaml"


def test_auth_paths_honor_biblebot_home(tmp_path):
    """Auth helpers should resolve paths from BIBLEBOT_HOME when set."""
    with patch.dict("os.environ", {paths.ENV_BIBLEBOT_HOME: str(tmp_path)}, clear=True):
        with patch.object(auth, "CONFIG_DIR", None), patch.object(
            auth, "CREDENTIALS_FILE", None
        ), patch.object(auth, "E2EE_STORE_DIR", None), patch("biblebot.auth.os.chmod"):
            assert auth.get_config_dir() == tmp_path
            assert auth.credentials_path() == tmp_path / "credentials.json"
            assert auth.get_store_dir() == tmp_path / "e2ee-store"
