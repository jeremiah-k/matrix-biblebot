"""Structured loading and normalization for BibleBot YAML configuration."""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from biblebot.constants.app import FILE_ENCODING_UTF8
from biblebot.constants.bible import (
    DEFAULT_TRANSLATION,
    TRANSLATION_ESV,
    TRANSLATION_KJV,
)
from biblebot.constants.config import (
    CONFIG_KEY_MATRIX,
    CONFIG_MATRIX_HOMESERVER,
    CONFIG_MATRIX_ROOM_IDS,
    CONFIG_MATRIX_USER,
)
from biblebot.constants.messages import MIN_MESSAGE_LENGTH


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
    except (yaml.YAMLError, UnicodeError):
        return _failure("invalid_yaml", f"Invalid YAML in config file {path}")

    return normalize_config(loaded, source=str(path))


def normalize_config(loaded: Any, *, source: str = "configuration") -> ConfigLoadResult:
    """Validate file or injected configuration with identical schema precedence.

    Nested matrix values take precedence over legacy keys even when empty.
    Optional null sections mean defaults. Unknown keys are retained so
    compatible additions do not require a schema version change.
    The caller's mapping is never mutated.
    """
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        return _failure(
            "root_not_mapping", f"Config root must be a mapping (dict) in {source}"
        )
    config = copy.deepcopy(loaded)
    converted_legacy = (
        CONFIG_MATRIX_ROOM_IDS in config and CONFIG_KEY_MATRIX not in config
    )
    for section in ("matrix", "bot", "api_keys", "logging"):
        value = config.get(section)
        if value is None:
            config[section] = {}
        elif not isinstance(value, dict):
            return _failure("section_not_mapping", f"'{section}' must be a mapping")

    matrix = config["matrix"]
    if "room_ids" in matrix:
        room_ids = matrix["room_ids"]
    else:
        room_ids = config.get(CONFIG_MATRIX_ROOM_IDS)
    if room_ids is None or room_ids == []:
        return _failure(
            "missing_room_ids", f"Missing required configuration: room_ids in {source}"
        )
    if not isinstance(room_ids, list):
        return _failure("room_ids_not_list", "'room_ids' must be a list in config")
    if any(
        not isinstance(room, str) or not re.fullmatch(r"[!#][^\s:]+:[^\s]+", room)
        for room in room_ids
    ):
        return _failure(
            "invalid_room_id",
            "Each room must be a non-empty Matrix ID (!room:server) or alias (#room:server)",
        )
    room_ids = list(dict.fromkeys(room_ids))
    matrix["room_ids"] = room_ids
    config[CONFIG_MATRIX_ROOM_IDS] = room_ids
    for legacy, nested in (
        (CONFIG_MATRIX_HOMESERVER, "homeserver"),
        (CONFIG_MATRIX_USER, "user"),
    ):
        if nested not in matrix and legacy in config:
            matrix[nested] = config[legacy]
        if nested in matrix and not isinstance(matrix[nested], str):
            return _failure(
                "invalid_matrix_value", f"'matrix.{nested}' must be a string"
            )

    for key in ("e2ee", "encryption"):
        if matrix.get(key) is None:
            if key in matrix:
                matrix[key] = {}
        elif not isinstance(matrix[key], dict):
            return _failure("section_not_mapping", f"'matrix.{key}' must be a mapping")
        if (
            key in matrix
            and "enabled" in matrix[key]
            and not isinstance(matrix[key]["enabled"], bool)
        ):
            return _failure(
                "invalid_boolean", f"'matrix.{key}.enabled' must be a YAML boolean"
            )
    if "e2ee" not in matrix and "encryption" in matrix:
        matrix["e2ee"] = matrix["encryption"]

    bot = config["bot"]
    translation = bot.get("default_translation", DEFAULT_TRANSLATION)
    if not isinstance(translation, str) or translation.strip().lower() not in (
        TRANSLATION_KJV,
        TRANSLATION_ESV,
    ):
        return _failure(
            "invalid_translation", "'bot.default_translation' must be kjv or esv"
        )
    if "default_translation" in bot:
        bot["default_translation"] = translation.strip().lower()
    for key in ("cache_enabled", "preserve_poetry_formatting"):
        if key in bot and not isinstance(bot[key], bool):
            return _failure("invalid_boolean", f"'bot.{key}' must be a YAML boolean")
    for key, minimum in (
        ("max_message_length", MIN_MESSAGE_LENGTH),
        ("split_message_length", 0),
    ):
        if key in bot and (type(bot[key]) is not int or bot[key] < minimum):
            return _failure(
                "invalid_message_length", f"'bot.{key}' must be an integer >= {minimum}"
            )
    for value in config["api_keys"].values():
        if value is not None and not isinstance(value, str):
            return _failure("invalid_api_key", "API keys must be strings or null")

    logging = config["logging"]
    levels = {"debug", "info", "warning", "error", "critical"}
    level = logging.get("level", "info")
    if not isinstance(level, str) or level.lower() not in levels:
        return _failure(
            "invalid_log_level", "'logging.level' must be a supported log level"
        )
    for key in ("color_enabled", "log_to_file"):
        if key in logging and not isinstance(logging[key], bool):
            return _failure(
                "invalid_boolean", f"'logging.{key}' must be a YAML boolean"
            )
    if logging.get("filename") is not None and not isinstance(logging["filename"], str):
        return _failure("invalid_log_filename", "'logging.filename' must be a string")
    count = logging.get("backup_count", 3)
    if type(count) is not int or count < 0:
        return _failure(
            "invalid_backup_count", "'logging.backup_count' must be an integer >= 0"
        )
    size = logging.get("max_log_size", 10)
    if isinstance(size, str):
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([kmgt]?i?b)?", size.strip().lower())
        valid_size = match is not None and float(match[1]) > 0
    else:
        valid_size = type(size) in (int, float) and math.isfinite(size) and size > 0
    if not valid_size:
        return _failure(
            "invalid_log_size",
            "'logging.max_log_size' must be a positive size in MB or with a unit (e.g. 10 MiB)",
        )
    debug = logging.get("debug")
    if debug is None:
        logging["debug"] = {}
    elif not isinstance(debug, dict):
        return _failure("section_not_mapping", "'logging.debug' must be a mapping")
    elif any(
        not isinstance(value, bool)
        and (not isinstance(value, str) or value.lower() not in levels)
        for value in debug.values()
    ):
        return _failure(
            "invalid_log_level",
            "Component debug settings must be booleans or supported log levels",
        )
    return ConfigLoadResult(config=config, converted_legacy=converted_legacy)


def e2ee_enabled(config: dict[str, Any]) -> bool:
    """Read encryption settings, preferring e2ee over its legacy alias."""
    matrix = config.get("matrix") or {}
    settings = matrix.get("e2ee", matrix.get("encryption")) or {}
    return settings.get("enabled", False) is True
