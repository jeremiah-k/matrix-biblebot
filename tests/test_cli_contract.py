"""Black-box contracts for the installed BibleBot command line."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the module entry point in a clean subprocess."""
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "biblebot", *args],
        check=False,
        capture_output=True,
        text=True,
        env=command_env,
    )


def test_help_uses_current_runtime_home():
    """Top-level help should describe the config path selected at invocation time."""
    runtime_home = Path("/tmp/BibleBot Contract Home")

    result = run_cli("--help", env={"BIBLEBOT_HOME": str(runtime_home)})

    assert result.returncode == 0
    normalized_help = " ".join(result.stdout.split())
    assert str(runtime_home / "config.yaml") in normalized_help
    assert result.stderr == ""


@pytest.mark.parametrize("command", ["config", "auth", "service"])
def test_incomplete_command_reports_usage_on_stderr(command: str):
    """A grouped command without an action should be a parser error, not a no-op."""
    result = run_cli(command)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "the following arguments are required: ACTION" in result.stderr


def test_partial_authentication_options_report_error_on_stderr_without_password():
    """Automation errors should use stderr and never repeat a supplied password."""
    password = "sentinel-password-value"  # noqa: S105

    result = run_cli(
        "auth",
        "login",
        "--username",
        "@bot:example.org",
        "--password",
        password,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Missing: --homeserver" in result.stderr
    assert password not in result.stderr


@pytest.mark.parametrize(
    ("field", "args"),
    [
        (
            "--homeserver",
            ["--homeserver", "", "--username", "@bot:example.org", "--password", "x"],
        ),
        (
            "--username",
            [
                "--homeserver",
                "https://example.org",
                "--username",
                "",
                "--password",
                "x",
            ],
        ),
    ],
)
def test_empty_required_authentication_option_reports_error_on_stderr(
    field: str, args: list[str]
):
    """Empty required values should fail through the command's error channel."""
    result = run_cli("auth", "login", *args)

    assert result.returncode == 1
    assert result.stdout == ""
    assert f"{field} must be non-empty" in result.stderr
