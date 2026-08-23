"""Pure planning and rendering for the BibleBot systemd user service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from biblebot.constants.app import SERVICE_DESCRIPTION


@dataclass(frozen=True, slots=True)
class ServicePlan:
    """All values required to render and write one user service unit."""

    service_path: Path
    command: tuple[str, ...]
    config_path: str
    working_directory: str
    environment: tuple[tuple[str, str], ...] = ()
    preserve_specifiers: bool = False
    description: str = SERVICE_DESCRIPTION


def quote_systemd_value(value: str, *, preserve_specifiers: bool = False) -> str:
    """Escape and quote one systemd value or command argument."""
    if not preserve_specifiers:
        value = value.replace("%", "%%")
    needs_quotes = any(char in value for char in (" ", "\t", '"', "\\", "$"))
    if not needs_quotes:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
    return f'"{escaped}"'


def _replace_or_add_setting(content: str, setting: str, value: str) -> str:
    replacement = f"{setting}={value}"
    content, replacements = re.subn(
        rf"^{re.escape(setting)}=.*$",
        replacement,
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if replacements:
        return content
    return re.sub(
        r"(?m)^\[Service\]\s*$",
        f"[Service]\n{replacement}",
        content,
        count=1,
    )


def _replace_or_add_environment(content: str, name: str, value: str) -> str:
    replacement = f"Environment={quote_systemd_value(f'{name}={value}')}"
    content, replacements = re.subn(
        rf'^Environment="?{re.escape(name)}=.*$',
        replacement,
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if replacements:
        return content
    return re.sub(
        r"(?m)^\[Service\]\s*$",
        f"[Service]\n{replacement}",
        content,
        count=1,
    )


def render_service_unit(template: str, plan: ServicePlan) -> str:
    """Render a deterministic systemd unit from a template and service plan."""
    content = template.replace("{SERVICE_DESCRIPTION}", plan.description)
    exec_start = " ".join(
        [
            *(
                quote_systemd_value(part, preserve_specifiers=plan.preserve_specifiers)
                for part in plan.command
            ),
            "--config",
            quote_systemd_value(
                plan.config_path, preserve_specifiers=plan.preserve_specifiers
            ),
        ]
    )
    content = _replace_or_add_setting(content, "ExecStart", exec_start)
    content = _replace_or_add_setting(
        content,
        "WorkingDirectory",
        quote_systemd_value(
            plan.working_directory, preserve_specifiers=plan.preserve_specifiers
        ),
    )
    for name, value in plan.environment:
        content = _replace_or_add_environment(content, name, value)
    if not content.endswith("\n"):
        content += "\n"
    return content
