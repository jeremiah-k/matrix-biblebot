"""Tests for pure systemd service planning and rendering."""

from pathlib import Path

from biblebot.service import ServicePlan, render_service_unit


BASE_TEMPLATE = """[Unit]
Description={SERVICE_DESCRIPTION}

[Service]
ExecStart=/old/biblebot
WorkingDirectory=/old/home
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""


def test_render_default_user_service_plan():
    plan = ServicePlan(
        service_path=Path("/home/user/.config/systemd/user/biblebot.service"),
        command=("/home/user/.local/bin/biblebot",),
        config_path="%h/.config/matrix-biblebot/config.yaml",
        working_directory="%h/.config/matrix-biblebot",
        preserve_specifiers=True,
    )

    rendered = render_service_unit(BASE_TEMPLATE, plan)

    assert "Description=Matrix Bible Bot Service" in rendered
    assert (
        "ExecStart=/home/user/.local/bin/biblebot --config "
        "%h/.config/matrix-biblebot/config.yaml" in rendered
    )
    assert "WorkingDirectory=%h/.config/matrix-biblebot" in rendered
    assert "BIBLEBOT_HOME=" not in rendered
    assert rendered.endswith("\n")


def test_render_portable_service_quotes_paths_and_sets_runtime_home(tmp_path: Path):
    runtime_home = tmp_path / 'BibleBot $Home "quoted"'
    plan = ServicePlan(
        service_path=tmp_path / "biblebot.service",
        command=("/opt/Bible Bot/python", "-m", "biblebot"),
        config_path=str(runtime_home / "config.yaml"),
        working_directory=str(runtime_home),
        environment=(("BIBLEBOT_HOME", str(runtime_home)),),
    )

    rendered = render_service_unit(BASE_TEMPLATE, plan)

    assert 'ExecStart="/opt/Bible Bot/python" -m biblebot --config ' in rendered
    assert "$$Home" in rendered
    assert '\\"quoted\\"' in rendered
    assert 'Environment="BIBLEBOT_HOME=' in rendered
    assert "Environment=PYTHONUNBUFFERED=1" in rendered


def test_render_service_unit_is_idempotent(tmp_path: Path):
    plan = ServicePlan(
        service_path=tmp_path / "biblebot.service",
        command=("/usr/bin/python3", "-m", "biblebot"),
        config_path="/srv/biblebot/config.yaml",
        working_directory="/srv/biblebot",
        environment=(("BIBLEBOT_HOME", "/srv/biblebot"),),
    )

    first = render_service_unit(BASE_TEMPLATE, plan)
    second = render_service_unit(first, plan)

    assert second == first
    assert second.count("ExecStart=") == 1
    assert second.count("WorkingDirectory=") == 1
    assert second.count("Environment=BIBLEBOT_HOME=") == 1


def test_render_adds_missing_service_settings(tmp_path: Path):
    plan = ServicePlan(
        service_path=tmp_path / "biblebot.service",
        command=("/usr/bin/biblebot",),
        config_path="/srv/biblebot/config.yaml",
        working_directory="/srv/biblebot",
    )

    rendered = render_service_unit("[Service]\nType=simple\n", plan)

    assert "ExecStart=/usr/bin/biblebot --config /srv/biblebot/config.yaml" in rendered
    assert "WorkingDirectory=/srv/biblebot" in rendered
