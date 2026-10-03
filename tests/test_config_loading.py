"""Tests for the structured configuration loading boundary."""

from pathlib import Path

import pytest

from biblebot.config import load_config_file


def test_load_nested_config_returns_normalized_result(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""
matrix:
  homeserver: https://example.org
  user: '@bot:example.org'
  room_ids:
    - '!room:example.org'
""".strip())

    result = load_config_file(config_path)

    assert result.ok is True
    assert result.diagnostics == ()
    assert result.converted_legacy is False
    assert result.config is not None
    assert result.config["matrix"]["room_ids"] == ["!room:example.org"]
    assert result.config["matrix_room_ids"] == ["!room:example.org"]


def test_load_legacy_config_preserves_keys_and_adds_nested_matrix(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""
matrix_homeserver: https://example.org
matrix_user: '@bot:example.org'
matrix_room_ids:
  - '!room:example.org'
""".strip())

    result = load_config_file(config_path)

    assert result.ok is True
    assert result.converted_legacy is True
    assert result.config is not None
    assert result.config["matrix_homeserver"] == "https://example.org"
    assert result.config["matrix"]["homeserver"] == "https://example.org"
    assert result.config["matrix"]["user"] == "@bot:example.org"
    assert result.config["matrix"]["room_ids"] == ["!room:example.org"]


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("- not\n- a\n- mapping\n", "root_not_mapping"),
        ("matrix: [unterminated\n", "invalid_yaml"),
        ("matrix:\n  homeserver: https://example.org\n", "missing_room_ids"),
        ("matrix:\n  room_ids: '!room:example.org'\n", "room_ids_not_list"),
    ],
)
def test_invalid_config_returns_stable_diagnostic(
    tmp_path: Path, content: str, code: str
):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(content)

    result = load_config_file(config_path)

    assert result.ok is False
    assert result.config is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [code]


def test_missing_config_returns_stable_diagnostic(tmp_path: Path):
    config_path = tmp_path / "missing.yaml"

    result = load_config_file(config_path)

    assert result.ok is False
    assert result.config is None
    assert result.diagnostics[0].code == "read_error"
    assert str(config_path) in result.diagnostics[0].message


def test_result_repr_does_not_include_config_secrets(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    secret = "sentinel-config-secret"  # noqa: S105
    config_path.write_text(
        f"matrix:\n  room_ids:\n    - '!room:example.org'\napi_keys:\n  esv: {secret}\n"
    )

    result = load_config_file(config_path)

    assert result.ok is True
    assert secret not in repr(result)
    assert result.config is not None
    assert result.config["api_keys"]["esv"] == secret


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("false", "root_not_mapping"),
        ("matrix: wrong\nmatrix_room_ids: ['!room:server']", "section_not_mapping"),
        (
            "matrix: {room_ids: []}\nmatrix_room_ids: ['!room:server']",
            "missing_room_ids",
        ),
        ("matrix: {room_ids: [17]}", "invalid_room_id"),
        ("matrix: {room_ids: ['not a room']}", "invalid_room_id"),
        (
            "matrix: {room_ids: ['!room:server'], e2ee: {enabled: 'false'}}",
            "invalid_boolean",
        ),
        (
            "matrix_room_ids: ['!room:server']\nbot: {cache_enabled: 'false'}",
            "invalid_boolean",
        ),
        (
            "matrix_room_ids: ['!room:server']\nbot: {max_message_length: text}",
            "invalid_message_length",
        ),
        (
            "matrix_room_ids: ['!room:server']\nbot: {default_translation: niv}",
            "invalid_translation",
        ),
        ("matrix_room_ids: ['!room:server']\napi_keys: {esv: 17}", "invalid_api_key"),
        (
            "matrix_room_ids: ['!room:server']\nlogging: {debug: true}",
            "section_not_mapping",
        ),
        (
            "matrix_room_ids: ['!room:server']\nlogging: {level: handlers}",
            "invalid_log_level",
        ),
        (
            "matrix_room_ids: ['!room:server']\nlogging: {max_log_size: -1}",
            "invalid_log_size",
        ),
    ],
)
def test_schema_errors_fail_at_loading(tmp_path, content, code):
    path = tmp_path / "config.yaml"
    path.write_text(content)
    result = load_config_file(path)
    assert not result.ok
    assert result.diagnostics[0].code == code


def test_null_optional_sections_and_legacy_encryption_are_normalized(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "matrix: {room_ids: ['!room:server'], encryption: {enabled: true}}\nbot: null\nlogging: null\napi_keys: null"
    )
    result = load_config_file(path)
    assert result.ok
    assert result.config["bot"] == {}
    assert result.config["matrix"]["e2ee"] == {"enabled": True}


def test_invalid_utf8_is_a_loading_diagnostic(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_bytes(b"\xff\xfe")
    assert not load_config_file(path).ok


def test_normalization_preserves_input_and_nested_precedence():
    from biblebot.config import normalize_config

    config = {
        "matrix": {"room_ids": ["!nested:server", "!nested:server"]},
        "matrix_room_ids": ["!legacy:server"],
    }
    result = normalize_config(config)
    assert result.ok
    assert result.config["matrix_room_ids"] == ["!nested:server"]
    assert config["matrix"]["room_ids"] == ["!nested:server", "!nested:server"]


@pytest.mark.asyncio
async def test_startup_rejects_encryption_without_saved_device(monkeypatch):
    from biblebot import bot

    monkeypatch.setattr(bot, "load_credentials", lambda: None)
    monkeypatch.setattr(bot, "load_environment", lambda *_args: ("token", {}))
    config = {"matrix": {"room_ids": ["!room:server"], "e2ee": {"enabled": True}}}
    with pytest.raises(RuntimeError, match="saved credentials with a device ID"):
        await bot.main(config=config)


@pytest.mark.parametrize("maximum", range(1, 9))
def test_message_limit_reserves_suffix_and_truncation_space(maximum):
    from biblebot.config import normalize_config

    result = normalize_config(
        {"matrix_room_ids": ["!room:server"], "bot": {"max_message_length": maximum}}
    )
    assert not result.ok
    assert result.diagnostics[0].code == "invalid_message_length"
