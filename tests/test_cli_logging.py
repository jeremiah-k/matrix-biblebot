"""CLI forwarding of explicit and configured logging levels."""

from unittest.mock import AsyncMock

import pytest

from biblebot import cli


@pytest.mark.parametrize("explicit_level", [None, "debug"])
def test_cli_forwards_only_an_explicit_log_level(monkeypatch, tmp_path, explicit_level):
    config = tmp_path / "config.yaml"
    config.write_text("matrix_room_ids: ['!room:server']")
    argv = ["biblebot", "--config", str(config)]
    if explicit_level is not None:
        argv.extend(["--log-level", explicit_level])
    monkeypatch.setattr("sys.argv", argv)
    run_bot = AsyncMock()
    monkeypatch.setattr(cli, "bot_main", run_bot)

    cli.main()

    expected = {} if explicit_level is None else {"log_level": explicit_level}
    run_bot.assert_awaited_once_with(str(config), **expected)
