"""Coverage for the `auth cross-sign` dispatch branch in handle_auth_command."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from biblebot import cli
from biblebot.auth import CrossSigningRefused


def _parse(*argv: str):
    parser, _, auth_parser, _ = cli.create_parser()
    return parser.parse_args(["auth", *argv]), auth_parser


class TestAuthCrossSignCommand:
    def test_success_prints_result_and_returns_zero(self, capsys):
        args, auth_parser = _parse("cross-sign")
        with patch(
            "biblebot.cli.ensure_bot_cross_signing",
            new=AsyncMock(return_value={"status": "ready"}),
        ) as mock_sign:
            status = cli.handle_auth_command(args, auth_parser)

        assert status == 0
        mock_sign.assert_awaited_once_with(bootstrap=False)
        assert "Cross-signing ready" in capsys.readouterr().out

    def test_bootstrap_flag_is_forwarded(self, capsys):
        args, auth_parser = _parse("cross-sign", "--bootstrap")
        with patch(
            "biblebot.cli.ensure_bot_cross_signing",
            new=AsyncMock(return_value={"status": "ready"}),
        ) as mock_sign:
            status = cli.handle_auth_command(args, auth_parser)

        assert status == 0
        mock_sign.assert_awaited_once_with(bootstrap=True)

    def test_cross_signing_refused_returns_one(self, capsys):
        args, auth_parser = _parse("cross-sign")
        with patch(
            "biblebot.cli.ensure_bot_cross_signing",
            new=AsyncMock(side_effect=CrossSigningRefused("would rotate identity")),
        ):
            status = cli.handle_auth_command(args, auth_parser)

        assert status == 1
        assert "Cross-signing refused: would rotate identity" in capsys.readouterr().out

    def test_unexpected_provider_error_logs_and_returns_one(self, capsys):
        args, auth_parser = _parse("cross-sign")
        with (
            patch(
                "biblebot.cli.ensure_bot_cross_signing",
                new=AsyncMock(side_effect=RuntimeError("nio exploded")),
            ),
            patch("biblebot.cli.logger") as mock_logger,
        ):
            status = cli.handle_auth_command(args, auth_parser)

        assert status == 1
        captured = capsys.readouterr()
        # The generic failure path must not leak the exception text to stdout
        assert "nio exploded" not in captured.out
        mock_logger.error.assert_called_once()
