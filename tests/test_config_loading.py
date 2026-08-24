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
