"""Structured loading and normalization for BibleBot YAML configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from biblebot.constants.app import FILE_ENCODING_UTF8
from biblebot.constants.config import (
    CONFIG_KEY_MATRIX,
    CONFIG_MATRIX_HOMESERVER,
    CONFIG_MATRIX_ROOM_IDS,
    CONFIG_MATRIX_USER,
)


@dataclass(frozen=True, slots=True)
class ConfigDiagnostic:
    """A stable configuration error suitable for CLI or log presentation."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ConfigLoadResult:
    """The normalized configuration and any loading diagnostics."""

    config: dict[str, Any] | None = field(repr=False)
    diagnostics: tuple[ConfigDiagnostic, ...] = ()
    converted_legacy: bool = False

    @property
    def ok(self) -> bool:
        """Return whether loading produced a usable configuration."""
        return self.config is not None and not self.diagnostics


def _failure(code: str, message: str) -> ConfigLoadResult:
    return ConfigLoadResult(
        config=None,
        diagnostics=(ConfigDiagnostic(code=code, message=message),),
    )


def load_config_file(config_file: str | Path) -> ConfigLoadResult:
    """Read, normalize, and validate a BibleBot YAML configuration file."""
    path = Path(config_file)
    try:
        with path.open("r", encoding=FILE_ENCODING_UTF8) as stream:
            loaded = yaml.safe_load(stream)
    except OSError:
        return _failure("read_error", f"Error loading config from {path}")
    except yaml.YAMLError:
        return _failure("invalid_yaml", f"Invalid YAML in config file {path}")

    config = loaded or {}
    if not isinstance(config, dict):
        return _failure(
            "root_not_mapping", f"Config root must be a mapping (dict) in {path}"
        )

    converted_legacy = (
        CONFIG_MATRIX_ROOM_IDS in config and CONFIG_KEY_MATRIX not in config
    )
    if converted_legacy:
        matrix_config: dict[str, Any] = {}
        if CONFIG_MATRIX_HOMESERVER in config:
            matrix_config["homeserver"] = config[CONFIG_MATRIX_HOMESERVER]
        if CONFIG_MATRIX_USER in config:
            matrix_config["user"] = config[CONFIG_MATRIX_USER]
        matrix_config["room_ids"] = config[CONFIG_MATRIX_ROOM_IDS]
        config[CONFIG_KEY_MATRIX] = matrix_config

    room_ids = None
    current_matrix = config.get(CONFIG_KEY_MATRIX)
    if isinstance(current_matrix, dict):
        room_ids = current_matrix.get("room_ids")
    if not room_ids and CONFIG_MATRIX_ROOM_IDS in config:
        room_ids = config[CONFIG_MATRIX_ROOM_IDS]

    if not room_ids:
        return _failure(
            "missing_room_ids", f"Missing required configuration: room_ids in {path}"
        )
    if not isinstance(room_ids, list):
        return _failure("room_ids_not_list", "'room_ids' must be a list in config")

    config[CONFIG_MATRIX_ROOM_IDS] = room_ids
    return ConfigLoadResult(config=config, converted_legacy=converted_legacy)
