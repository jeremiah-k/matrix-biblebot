"""Service installation failure is visible in the CLI exit status."""

from unittest.mock import Mock

import pytest

from biblebot import cli, setup_utils


def test_service_install_failure_exits_unsuccessfully(monkeypatch):
    monkeypatch.setattr("sys.argv", ["biblebot", "service", "install"])
    install = Mock(return_value=False)
    monkeypatch.setattr(setup_utils, "install_service", install)

    with pytest.raises(SystemExit) as failure:
        cli.main()

    assert failure.value.code == 1
    install.assert_called_once_with()
