"""Behavioral tests for BibleBot runtime path resolution."""

import shutil
from pathlib import Path

from biblebot import auth, cli, constants, paths, setup_utils
from biblebot.constants import config as config_constants


def test_unset_runtime_home_preserves_default_config_layout(monkeypatch, tmp_path):
    """Config files keep their historical XDG config-home location."""
    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    expected_home = tmp_path / ".config" / "matrix-biblebot"
    assert paths.get_home_dir() == expected_home
    assert paths.get_config_path() == expected_home / "config.yaml"
    assert paths.get_credentials_path() == expected_home / "credentials.json"


def test_state_paths_follow_xdg_state_home(monkeypatch, tmp_path):
    """E2EE store and logs are runtime state and live under XDG_STATE_HOME."""
    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    state_home = tmp_path / ".local" / "state" / "matrix-biblebot"
    assert paths.get_e2ee_store_dir() == state_home / "e2ee-store"
    assert paths.get_log_dir() == state_home / "logs"


def test_unset_runtime_home_preserves_xdg_config_layout(monkeypatch, tmp_path):
    """XDG_CONFIG_HOME should remain the fallback when BIBLEBOT_HOME is unset."""
    xdg_home = tmp_path / "xdg"
    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))

    assert paths.get_home_dir() == xdg_home / "matrix-biblebot"


def test_xdg_state_home_controls_state_paths(monkeypatch, tmp_path):
    """XDG_STATE_HOME should control the E2EE store and log locations."""
    state_home = tmp_path / "xdg-state"
    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))

    assert paths.get_e2ee_store_dir() == state_home / "matrix-biblebot" / "e2ee-store"
    assert paths.get_log_dir() == state_home / "matrix-biblebot" / "logs"


def test_biblebot_home_keeps_single_directory_layout(monkeypatch, tmp_path):
    """BIBLEBOT_HOME still places everything under one portable directory."""
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("BIBLEBOT_HOME", str(runtime_home))

    assert paths.get_config_path() == runtime_home / "config.yaml"
    assert paths.get_credentials_path() == runtime_home / "credentials.json"
    assert paths.get_e2ee_store_dir() == runtime_home / "e2ee-store"
    assert paths.get_log_dir() == runtime_home / "logs"


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


def test_legacy_e2ee_store_is_migrated_to_state_home(monkeypatch, tmp_path):
    """A pre-existing store in the old location moves into the state home."""
    legacy_store = tmp_path / ".config" / "matrix-biblebot" / "e2ee-store"
    legacy_store.mkdir(parents=True)
    (legacy_store / "device.db").touch()

    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    resolved = paths.get_e2ee_store_dir()

    new_store = tmp_path / ".local" / "state" / "matrix-biblebot" / "e2ee-store"
    assert resolved == new_store
    assert (new_store / "device.db").exists()
    assert not legacy_store.exists()


def test_failed_migration_falls_back_to_legacy_location(monkeypatch, tmp_path, caplog):
    """If the move fails, the bot keeps using the legacy path for this run."""
    import logging

    legacy_store = tmp_path / ".config" / "matrix-biblebot" / "e2ee-store"
    legacy_store.mkdir(parents=True)
    (legacy_store / "device.db").touch()

    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(paths.shutil, "move", raise_os_error)

    with caplog.at_level(logging.WARNING):
        resolved = paths.get_e2ee_store_dir()

    assert resolved == legacy_store
    assert legacy_store.exists()
    assert any("Could not migrate" in record.message for record in caplog.records)


def test_partial_migration_failure_cleans_target_and_falls_back(monkeypatch, tmp_path):
    """A shutil.Error from a partial copy must not leave a broken target.

    shutil.move falls back to copytree across filesystems; an interrupted
    copy can leave the target present but incomplete. The resolver must
    clean it up and fall back to the intact legacy store.
    """
    legacy_store = tmp_path / ".config" / "matrix-biblebot" / "e2ee-store"
    legacy_store.mkdir(parents=True)
    (legacy_store / "device.db").touch()

    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    def partial_move(_source, target):
        Path(target).mkdir(parents=True)
        raise shutil.Error([("source", str(target), "copy failed")])

    monkeypatch.setattr(paths.shutil, "move", partial_move)

    resolved = paths.get_e2ee_store_dir()

    assert resolved == legacy_store
    assert (legacy_store / "device.db").exists()


def test_lost_race_does_not_overwrite_other_process_migration(monkeypatch, tmp_path):
    """When two processes race to migrate the same legacy store, neither may
    delete the target the other created.

    The TOCTOU window: process A starts the move while process B is past the
    pre-check but hasn't entered shutil.move yet. A succeeds; B sees legacy
    gone and must not delete target. The resolver must treat the
    FileNotFoundError from the move as a successful migration and trust the
    target already there.
    """
    legacy_store = tmp_path / ".config" / "matrix-biblebot" / "e2ee-store"
    legacy_store.mkdir(parents=True)
    (legacy_store / "device.db").write_bytes(b"original-keys")

    target = tmp_path / ".local" / "state" / "matrix-biblebot" / "e2ee-store"

    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    moved_keys = b""

    def losing_race_move(_source, target):
        # The winning process already moved the store. Simulate the legacy
        # directory disappearing and the target containing its data.
        target_path = Path(target)
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / "device.db").write_bytes(moved_keys)
        if legacy_store.exists():
            shutil.rmtree(legacy_store)
        raise FileNotFoundError(2, "No such file", str(legacy_store))

    moved_keys = b"migrated-by-other-process"
    monkeypatch.setattr(paths.shutil, "move", losing_race_move)

    resolved = paths.get_e2ee_store_dir()

    assert resolved == target
    # The migration performed by the other process must be intact.
    assert (target / "device.db").read_bytes() == moved_keys


def test_migrator_does_not_clobber_target_published_during_move(monkeypatch, tmp_path):
    """If shutil.move partially succeeds and a peer publishes target before we
    roll back, the rollback must not delete the peer's data.
    """
    legacy_store = tmp_path / ".config" / "matrix-biblebot" / "e2ee-store"
    legacy_store.mkdir(parents=True)
    (legacy_store / "device.db").touch()

    target = tmp_path / ".local" / "state" / "matrix-biblebot" / "e2ee-store"

    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    peer_state = {"phase": "before"}

    def failing_then_peer_writes(source, target):
        target_path = Path(target)
        if peer_state["phase"] == "before":
            target_path.mkdir(parents=True)
            peer_state["phase"] = "failed"
            raise shutil.Error([("source", str(target), "copy failed")])
        # Peer races past our roll-back and writes the real data.
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / "device.db").write_bytes(b"peers-keys")

    monkeypatch.setattr(paths.shutil, "move", failing_then_peer_writes)

    # First call: our move fails; rollback runs against the partial copy.
    resolved = paths.get_e2ee_store_dir()
    assert resolved == legacy_store

    # Second call (simulates a second migration attempt): peer has finished
    # writing real data; the move should now see target.exists() and not
    # touch it.
    peer_state["phase"] = "after"
    resolved_again = paths.get_e2ee_store_dir()
    assert resolved_again == target
    assert (target / "device.db").read_bytes() == b"peers-keys"


def raise_os_error(*_args, **_kwargs):
    raise OSError("permission denied")


def test_no_migration_when_new_store_already_exists(monkeypatch, tmp_path):
    """An existing state-home store must never be clobbered by migration."""
    legacy_store = tmp_path / ".config" / "matrix-biblebot" / "e2ee-store"
    legacy_store.mkdir(parents=True)
    (legacy_store / "old-device.db").touch()

    monkeypatch.delenv("BIBLEBOT_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    new_store = tmp_path / ".local" / "state" / "matrix-biblebot" / "e2ee-store"
    new_store.mkdir(parents=True)
    (new_store / "new-device.db").touch()

    assert paths.get_e2ee_store_dir() == new_store
    assert (new_store / "new-device.db").exists()
    # Legacy directory left in place; user data is never silently discarded.
    assert (legacy_store / "old-device.db").exists()


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
