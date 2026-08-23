"""Behavioral tests for BibleBot runtime path resolution."""

from pathlib import Path

from biblebot import auth, cli, constants, paths, setup_utils
from biblebot.constants import config as config_constants


def test_unset_runtime_home_preserves_default_layout(monkeypatch, tmp_path):
    """Without overrides, BibleBot should retain its historical config home."""
    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    expected_home = tmp_path / ".config" / "matrix-biblebot"
    assert paths.get_home_dir() == expected_home
    assert paths.get_config_path() == expected_home / "config.yaml"
    assert paths.get_credentials_path() == expected_home / "credentials.json"
    assert paths.get_e2ee_store_dir() == expected_home / "e2ee-store"


def test_unset_runtime_home_preserves_xdg_layout(monkeypatch, tmp_path):
    """XDG_CONFIG_HOME should remain the fallback when BIBLEBOT_HOME is unset."""
    xdg_home = tmp_path / "xdg"
    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))

    assert paths.get_home_dir() == xdg_home / "matrix-biblebot"


def test_biblebot_home_controls_default_config_after_import(monkeypatch, tmp_path):
    """The runtime home should be read when a path is requested."""
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("BIBLEBOT_HOME", str(runtime_home))

    assert cli.get_default_config_path() == runtime_home / "config.yaml"


def test_relative_biblebot_home_is_made_absolute(monkeypatch, tmp_path):
    """Relative runtime homes should not depend on a later working directory."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BIBLEBOT_HOME", "nested/runtime-home")

    assert paths.get_home_dir() == tmp_path / "nested" / "runtime-home"


def test_biblebot_home_controls_credentials_after_import(monkeypatch, tmp_path):
    """Credentials should use and safely create the current runtime home."""
    runtime_home = tmp_path / "nested" / "runtime-home"
    monkeypatch.setenv("BIBLEBOT_HOME", str(runtime_home))

    assert auth.credentials_path() == runtime_home / "credentials.json"
    assert runtime_home.is_dir()


def test_biblebot_home_controls_e2ee_store_after_import(monkeypatch, tmp_path):
    """The E2EE store should follow environment changes after module import."""
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("BIBLEBOT_HOME", str(runtime_home))

    assert auth.get_store_dir() == runtime_home / "e2ee-store"


def test_path_constants_follow_environment_changes(monkeypatch, tmp_path):
    """Compatibility constants should delegate to the same path authority."""
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("BIBLEBOT_HOME", str(runtime_home))

    assert config_constants.CONFIG_DIR == runtime_home
    assert config_constants.CREDENTIALS_FILE == runtime_home / "credentials.json"
    assert config_constants.E2EE_STORE_DIR == runtime_home / "e2ee-store"


def test_reexported_path_constants_follow_environment_changes(monkeypatch, tmp_path):
    """Package-level compatibility exports should not retain stale paths."""
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("BIBLEBOT_HOME", str(runtime_home))

    assert constants.CONFIG_DIR == runtime_home
    assert constants.CREDENTIALS_FILE == runtime_home / "credentials.json"
    assert constants.E2EE_STORE_DIR == runtime_home / "e2ee-store"


def test_service_uses_runtime_home_for_all_runtime_paths(monkeypatch, tmp_path):
    """An installed service should keep config and state in BIBLEBOT_HOME."""
    runtime_home = tmp_path / "runtime home"
    service_path = tmp_path / "systemd" / "biblebot.service"
    template = """[Service]
ExecStart=%h/.local/bin/biblebot --config %h/.config/matrix-biblebot/config.yaml
WorkingDirectory=%h/.config/matrix-biblebot
Environment=PYTHONUNBUFFERED=1
"""
    monkeypatch.setenv("BIBLEBOT_HOME", str(runtime_home))
    monkeypatch.setattr(setup_utils, "get_executable_path", lambda: "/usr/bin/biblebot")
    monkeypatch.setattr(setup_utils, "get_template_service_content", lambda: template)
    monkeypatch.setattr(setup_utils, "get_user_service_path", lambda: service_path)

    assert setup_utils.create_service_file() is True

    service = service_path.read_text(encoding="utf-8")
    assert (
        f'ExecStart=/usr/bin/biblebot --config "{runtime_home}/config.yaml"' in service
    )
    assert f'WorkingDirectory="{runtime_home}"' in service
    assert f'Environment="BIBLEBOT_HOME={runtime_home}"' in service
    assert runtime_home.is_dir()
