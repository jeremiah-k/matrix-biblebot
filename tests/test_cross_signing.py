"""Tests for the explicit, self-managed bot cross-signing flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biblebot import auth, cli


@pytest.fixture
def credentials():
    return auth.Credentials(
        homeserver="https://matrix.example.org",
        user_id="@bot:example.org",
        access_token="secret-token",  # noqa: S106 - test fixture value
        device_id="BOTDEVICE",
    )


@pytest.mark.asyncio
async def test_cross_signing_restores_session_and_closes_client(credentials, tmp_path):
    sidecar = tmp_path / "@bot:example.org_cross_signing.json"
    sidecar.write_text("{}", encoding="utf-8")
    client = MagicMock()
    client.ensure_cross_signing = AsyncMock(return_value={"status": "ready"})
    client.close = AsyncMock()

    with (
        patch.object(auth, "load_credentials", return_value=credentials),
        patch.object(auth, "E2EE_STORE_DIR", tmp_path),
        patch.object(auth, "AsyncClient", return_value=client),
        patch("getpass.getpass", return_value="matrix-password") as prompt,
    ):
        result = await auth.ensure_bot_cross_signing()

    assert result == {"status": "ready"}
    client.restore_login.assert_called_once_with(
        user_id=credentials.user_id,
        device_id=credentials.device_id,
        access_token=credentials.access_token,
    )
    client.ensure_cross_signing.assert_awaited_once_with(
        password="matrix-password"  # noqa: S106 - test fixture value
    )
    client.close.assert_awaited_once()
    prompt.assert_called_once()


@pytest.mark.asyncio
async def test_cross_signing_refuses_missing_sidecar_without_bootstrap(
    credentials, tmp_path
):
    with (
        patch.object(auth, "load_credentials", return_value=credentials),
        patch.object(auth, "E2EE_STORE_DIR", tmp_path),
        patch.object(auth, "AsyncClient") as client_factory,
        pytest.raises(auth.CrossSigningRefused, match="no local cross-signing sidecar"),
    ):
        await auth.ensure_bot_cross_signing()

    client_factory.assert_not_called()


@pytest.mark.asyncio
async def test_cross_signing_explicit_bootstrap_allows_missing_sidecar(
    credentials, tmp_path
):
    client = MagicMock()
    client.ensure_cross_signing = AsyncMock(return_value={"status": "created"})
    client.close = AsyncMock()

    with (
        patch.object(auth, "load_credentials", return_value=credentials),
        patch.object(auth, "E2EE_STORE_DIR", tmp_path),
        patch.object(auth, "AsyncClient", return_value=client),
        patch("getpass.getpass", return_value="password"),
    ):
        result = await auth.ensure_bot_cross_signing(bootstrap=True)

    assert result == {"status": "created"}
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cross_signing_refuses_ambiguous_sidecars(credentials, tmp_path):
    (tmp_path / "one_cross_signing.json").write_text("{}", encoding="utf-8")
    (tmp_path / "two_cross_signing.json").write_text("{}", encoding="utf-8")

    with (
        patch.object(auth, "load_credentials", return_value=credentials),
        patch.object(auth, "E2EE_STORE_DIR", tmp_path),
        patch.object(auth, "AsyncClient") as client_factory,
        pytest.raises(auth.CrossSigningRefused, match="ambiguous"),
    ):
        await auth.ensure_bot_cross_signing()

    client_factory.assert_not_called()


@pytest.mark.asyncio
async def test_cross_signing_closes_client_when_ensure_fails(credentials, tmp_path):
    (tmp_path / "@bot:example.org_cross_signing.json").write_text(
        "{}", encoding="utf-8"
    )
    client = MagicMock()
    client.ensure_cross_signing = AsyncMock(side_effect=RuntimeError("upload failed"))
    client.close = AsyncMock()

    with (
        patch.object(auth, "load_credentials", return_value=credentials),
        patch.object(auth, "E2EE_STORE_DIR", tmp_path),
        patch.object(auth, "AsyncClient", return_value=client),
        patch("getpass.getpass", return_value="password"),
        pytest.raises(RuntimeError, match="upload failed"),
    ):
        await auth.ensure_bot_cross_signing()

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cross_signing_does_not_persist_password(credentials, tmp_path):
    (tmp_path / "@bot:example.org_cross_signing.json").write_text(
        "{}", encoding="utf-8"
    )
    client = MagicMock()
    client.ensure_cross_signing = AsyncMock(return_value={"status": "already_ready"})
    client.close = AsyncMock()

    with (
        patch.object(auth, "load_credentials", return_value=credentials),
        patch.object(auth, "save_credentials") as save,
        patch.object(auth, "E2EE_STORE_DIR", tmp_path),
        patch.object(auth, "AsyncClient", return_value=client),
        patch("getpass.getpass", return_value="never-save-me"),
    ):
        result = await auth.ensure_bot_cross_signing()

    assert result == {"status": "already_ready"}
    save.assert_not_called()
    assert "never-save-me" not in credentials.to_dict().values()


def test_cross_signing_cli_dispatches_explicit_bootstrap():
    with (
        patch("sys.argv", ["biblebot", "auth", "cross-sign", "--bootstrap"]),
        patch.object(cli, "ensure_bot_cross_signing", new_callable=AsyncMock) as ensure,
    ):
        ensure.return_value = {"status": "created"}
        with pytest.raises(SystemExit) as exc:
            cli.main()

    assert exc.value.code == 0
    ensure.assert_awaited_once_with(bootstrap=True)
