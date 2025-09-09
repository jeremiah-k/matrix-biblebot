"""
Setup utilities for BibleBot.

This module provides functions for managing the systemd user service
and related configuration tasks.
"""

import getpass
import importlib.resources
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from biblebot.constants.app import (
    APP_NAME,
    DIR_SHARE,
    DIR_TOOLS,
    EXECUTABLE_NAME,
    FILE_MODE_READ,
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
)
from biblebot.constants.config import CONFIG_DIR, ENV_USER, ENV_USERNAME
from biblebot.constants.messages import WARNING_EXECUTABLE_NOT_FOUND
from biblebot.constants.system import (
    DEFAULT_CONFIG_PATH,
    LOCAL_SHARE_DIR,
    PIPX_VENV_PATH,
    SYSTEMCTL_ARG_IS_ENABLED,
    SYSTEMCTL_ARG_USER,
    SYSTEMCTL_COMMANDS,
    SYSTEMCTL_PATH,
    SYSTEMD_USER_DIR,
)
from biblebot.tools import copy_service_template_to


def get_executable_path():
    """
    Return the full path to the biblebot executable.

    Attempts to locate an installed `biblebot` entry point using the system PATH (suitable for pipx or pip installs).
    If found, returns that executable path; if not found, returns the current Python interpreter path (sys.executable) as a fallback.
    This function prints either the discovered executable path or a warning message when falling back.
    """
    biblebot_path = shutil.which(EXECUTABLE_NAME)
    if biblebot_path:
        print(f"Found biblebot executable at: {biblebot_path}")
        return biblebot_path
    else:
        print(WARNING_EXECUTABLE_NOT_FOUND)
        return sys.executable


def get_user_service_path():
    """
    Return the filesystem path to the user's systemd service file for the application.

    Returns:
        pathlib.Path: Full path to the user service file (SYSTEMD_USER_DIR / SERVICE_NAME).
    """
    return SYSTEMD_USER_DIR / SERVICE_NAME


def service_exists():
    """
    Return True if the user systemd service file exists.

    Checks for the presence of the service unit file at the path returned by get_user_service_path().

    Returns:
        bool: True if the service file exists, False otherwise.
    """
    return get_user_service_path().exists()


def print_service_commands():
    """Print the commands for controlling the systemd user service."""
    if not SYSTEMCTL_COMMANDS:
        print("  systemctl commands not available on this system.")
        return

    order = [
        ("start", "# Start the service"),
        ("stop", "# Stop the service"),
        ("restart", "# Restart the service"),
        ("status", "# Check service status"),
    ]
    for key, comment in order:
        cmd = SYSTEMCTL_COMMANDS.get(key)
        if not cmd:
            continue
        if isinstance(cmd, (list, tuple)):
            printable = shlex.join([str(c) for c in cmd])
        else:
            printable = str(cmd)
        print(f"  {printable}  {comment}")


def read_service_file():
    """Read the content of the service file if it exists."""
    service_path = get_user_service_path()
    if service_path.exists():
        return service_path.read_text(encoding="utf-8")
    return None


def get_template_service_path():
    """
    Locate the systemd service template file for the application.

    Searches a series of likely locations (package directory, package tools subdir,
    system-wide share under sys.prefix, user local share, several development
    paths relative to the package, and the current working directory) and returns
    the first existing path.

    Returns:
        pathlib.Path | None: Absolute path to the first found template file, or None if no
        candidate exists.
    """
    # Try to find the service template file in various locations (Path-based)
    pkg = Path(__file__).parent
    # Find repository root by looking for marker files (more robust than fixed depth)
    repo_root = None
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".git").exists() or (parent / "setup.py").exists():
            repo_root = parent
            break
    # No fallback - if no repo marker is found, repo_root stays None

    template_paths = [
        # Package dir (post-install)
        pkg / SERVICE_NAME,
        # Package tools subdir
        pkg / DIR_TOOLS / SERVICE_NAME,
        # sys.prefix share dirs
        Path(sys.prefix) / DIR_SHARE / APP_NAME / SERVICE_NAME,
        Path(sys.prefix) / DIR_SHARE / APP_NAME / DIR_TOOLS / SERVICE_NAME,
        # User local share
        LOCAL_SHARE_DIR / APP_NAME / SERVICE_NAME,
        LOCAL_SHARE_DIR / APP_NAME / DIR_TOOLS / SERVICE_NAME,
        # One level up from package (dev)
        pkg.parent / DIR_TOOLS / SERVICE_NAME,
        # Two levels up (dev)
        pkg.parent.parent / DIR_TOOLS / SERVICE_NAME,
        # CWD fallback
        Path.cwd() / DIR_TOOLS / SERVICE_NAME,
    ]

    # Add repo root path only if we found a valid repository
    if repo_root is not None:
        template_paths.insert(-1, repo_root / DIR_TOOLS / SERVICE_NAME)

    # Try each path until we find one that exists
    for p in template_paths:
        if p.is_file():
            return p

    # If we get here, we couldn't find the template
    return None


def get_template_service_content():
    """
    Return the systemd service template content to use when creating the user service.

    Tries the following sources in order and returns the first successfully read content:
    1. A stable copy provided by copy_service_template_to(...).
    2. The packaged resource `biblebot.tools:biblebot.service` via importlib.resources.
    3. A path found by get_template_service_path().

    If none of the sources can be read, returns a built-in default service template string suitable for a typical user install.
    """
    # Use the copy helper function to get a stable template file
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, "service_template.service")
            template_path = copy_service_template_to(temp_file_path)
            with open(template_path, FILE_MODE_READ, encoding="utf-8") as f:
                service_template = f.read()
            return service_template
    except (OSError, ValueError) as e:
        print(f"Error reading service template: {e}")
        # Let unexpected exceptions surface for better debugging

    # If the helper function failed, try using importlib.resources directly
    try:
        service_template = (
            importlib.resources.files("biblebot.tools")
            .joinpath("biblebot.service")
            .read_text(encoding="utf-8")
        )
        return service_template
    except (FileNotFoundError, ImportError, OSError) as e:
        print(f"Error accessing biblebot.service via importlib.resources: {e}")

        # Fall back to the file path method
        template_path = get_template_service_path()
        if template_path:
            # Read the template from file
            try:
                with open(template_path, FILE_MODE_READ, encoding="utf-8") as f:
                    service_template = f.read()
                return service_template
            except OSError as e:
                print(f"Error reading service template file: {e}")

    # If we couldn't find or read the template file, use a default template
    print("Using default service template")
    return """[Unit]
Description={SERVICE_DESCRIPTION}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
# The biblebot binary can be installed via pipx or pip
ExecStart=%h/.local/bin/biblebot --config %h/.config/matrix-biblebot/config.yaml
WorkingDirectory=%h/.config/matrix-biblebot
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1
# Ensure both pipx and pip environments are properly loaded
Environment=PATH=%h/.local/bin:%h/.local/pipx/venvs/matrix-biblebot/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
"""


def is_service_enabled():
    """
    Return True if the user systemd service is enabled to start at boot.

    Performs `systemctl --user is-enabled <SERVICE_NAME>` using SYSTEMCTL_PATH; returns True when the command exits successfully (exit code 0). Any execution error yields False.

    Returns:
        bool: True when the service is enabled, False otherwise (including on errors).
    """
    if SYSTEMCTL_PATH is None:
        return False
    try:
        result = subprocess.run(
            [
                SYSTEMCTL_PATH,
                SYSTEMCTL_ARG_USER,
                SYSTEMCTL_ARG_IS_ENABLED,
                SERVICE_NAME,
            ],
            check=False,  # Don't raise an exception if the service is not enabled
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def is_service_active():
    """
    Return True if the BibleBot user systemd service is currently active (running), otherwise False.

    Checks the service status by invoking `systemctl --user is-active <SERVICE_NAME>`. Any errors or unexpected results are treated as the service not being active and result in False.
    """
    if SYSTEMCTL_PATH is None:
        return False
    try:
        result = subprocess.run(
            [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "is-active", SERVICE_NAME],
            check=False,  # Don't raise an exception if the service is not active
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "active"
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def create_service_file():
    """
    Create or update the systemd user service file for BibleBot.

    Determines the best command to start BibleBot (prefers an installed `biblebot` executable on PATH;
    falls back to invoking the package with the current Python interpreter using `-m biblebot`),
    injects that command into a service template as the `ExecStart` value (including the
    DEFAULT_CONFIG_PATH `--config` argument), and writes the resulting unit to the user's
    systemd service path.

    Side effects:
    - Ensures the user systemd service directory and the application config directory exist.
    - Reads the service template via get_template_service_content().
    - Writes the final service unit to get_user_service_path().
    - Prints status and error messages to stdout/stderr.

    Returns:
        bool: True if the service file was successfully created/updated, False on failure
        (including template resolution or I/O errors).
    """
    executable_path = get_executable_path()
    if not executable_path:
        print("Error: Could not determine a command to start biblebot")
        return False

    # Create service directory if it doesn't exist
    service_dir = get_user_service_path().parent
    service_dir.mkdir(parents=True, exist_ok=True)

    # Create config directory if it doesn't exist
    config_dir = CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)

    # Get the template service content
    service_template = get_template_service_content()
    if not service_template:
        print("Error: Could not find service template file")
        return False

    # Fill optional description placeholder if present
    service_template = service_template.replace(
        "{SERVICE_DESCRIPTION}", SERVICE_DESCRIPTION
    )

    # Compute ExecStart command
    # If get_executable_path returned the python interpreter, use module form
    exec_cmd = executable_path
    if exec_cmd == sys.executable:
        exec_cmd = f"{shlex.quote(sys.executable)} -m biblebot"
    else:
        exec_cmd = shlex.quote(exec_cmd)

    # Replace ExecStart line to use discovered command and default config path
    exec_start_line = f'ExecStart={exec_cmd} --config "{DEFAULT_CONFIG_PATH}"'
    service_content, n = re.subn(
        r"^ExecStart=.*$",
        exec_start_line,
        service_template,
        count=1,
        flags=re.MULTILINE,
    )
    if n == 0:
        service_content = re.sub(
            r"(?m)^\[Service\]\s*$",
            f"[Service]\n{exec_start_line}",
            service_template,
        )
    if not service_content.endswith("\n"):
        service_content += "\n"

    # Write service file
    try:
        get_user_service_path().write_text(service_content, encoding="utf-8")
        print(f"Service file created at {get_user_service_path()}")
        return True
    except (IOError, OSError) as e:
        print(f"Error creating service file: {e}")
        return False


def reload_daemon():
    """
    Reload the systemd user daemon.

    Runs the configured systemctl command (via SYSTEMCTL_PATH) with the `--user daemon-reload`
    action to make systemd pick up changes to user units.

    Returns:
        bool: True if the daemon-reload command completed successfully; False on failure
        (command returned non-zero or an OSError occurred).
    """
    if SYSTEMCTL_PATH is None:
        print("systemctl not available on this system")
        return False
    try:
        # Using absolute path for security
        subprocess.run(
            [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "daemon-reload"], check=True
        )
        print("Systemd user daemon reloaded")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error reloading systemd daemon: {e}")
        return False
    except OSError as e:
        print(f"Error: {e}")
        return False


def service_needs_update():
    """
    Determine whether the installed user systemd service file needs updating.

    Performs these checks in order and returns the first applicable result:
    - If no installed service file exists -> needs update.
    - If a template service file cannot be located -> reports no update (template missing).
    - If the discovered start command for the current installation cannot be determined -> reports no update.
    - If the service's ExecStart line does not match the installation's expected command (either the Python `-m biblebot` form or the discovered executable) -> needs update.
    - If the service file's PATH does not include the configured pipx venv path -> needs update.
    - If the template file's modification time is newer than the installed service file -> needs update.
    If none of the above indicate an update is necessary, reports the service file as up to date.

    Returns:
        tuple: (needs_update: bool, reason: str) — `needs_update` is True when an update is required; `reason` is a short explanation.
    """
    # Check if service already exists
    existing_service = read_service_file()
    if not existing_service:
        return True, "No existing service file found"

    # Get the template service path
    template_path = get_template_service_path()
    if not template_path:
        return False, "Could not find template service file"

    # Get the executable path
    executable_path = get_executable_path()
    if not executable_path:
        return False, "Could not determine biblebot start command"

    # Build variants that mirror create_service_file() quoting to avoid false positives
    acceptable_snippets: list[str] = []
    if executable_path == sys.executable:
        acceptable_snippets.extend(
            [
                f"{shlex.quote(sys.executable)} -m biblebot",
                f"{sys.executable} -m biblebot",
            ]
        )
    else:
        acceptable_snippets.extend(
            [
                shlex.quote(executable_path),
                executable_path,
            ]
        )
    # Focus only on the ExecStart= line to reduce accidental matches
    execstart_line = next(
        (
            ln
            for ln in existing_service.splitlines()
            if ln.strip().startswith("ExecStart=")
        ),
        "",
    )

    # Check if the ExecStart uses a valid command
    if not any(snippet in execstart_line for snippet in acceptable_snippets):
        return True, "Service file ExecStart does not match the current installation"

    # Check if the PATH environment includes pipx paths
    # Detect pipx requirement from the unit body itself
    requires_pipx = "pipx" in existing_service
    pipx_ok = (str(PIPX_VENV_PATH) in existing_service) or (
        "pipx/venvs" in existing_service
    )
    if requires_pipx and not pipx_ok:
        return True, "Service file does not include pipx paths in PATH environment"

    # Check if the service file has been modified recently
    try:
        template_mtime = template_path.stat().st_mtime
        service_path = get_user_service_path()
        if service_path.exists():
            service_mtime = service_path.stat().st_mtime
            if template_mtime > service_mtime:
                return (
                    True,
                    "Template service file is newer than installed service file",
                )
    except OSError:
        # If either file vanished mid-check, don't force an update here.
        pass

    return False, "Service file is up to date"


def check_loginctl_available():
    """Check if loginctl is available on the system.

    Returns:
        bool: True if loginctl is available, False otherwise.
    """
    try:
        return shutil.which("loginctl") is not None
    except (OSError, TypeError):
        return False


def _get_current_username() -> str:
    """Get the current username from environment variables or system."""
    return os.environ.get(ENV_USER) or os.environ.get(ENV_USERNAME) or getpass.getuser()


def check_lingering_enabled():
    """
    Return True if user lingering (systemd --user Linger) is enabled for the current user.

    This inspects the environment variables ENV_USER then ENV_USERNAME to determine the target username
    and runs `loginctl show-user <username> --property=Linger`. Returns True when the command
    succeeds and reports `Linger=yes`. Any error (including missing username or command failure)
    results in False.
    """
    try:
        username = _get_current_username()
        result = subprocess.run(
            ["loginctl", "show-user", username, "--property=Linger"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "Linger=yes" in result.stdout
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def enable_lingering():
    """
    Enable systemd "lingering" for the current user by running `sudo loginctl enable-linger <username>`.

    Determines the target username from the environment variables ENV_USER or ENV_USERNAME and invokes `sudo loginctl enable-linger`. Returns True if the command exits with status 0; returns False on nonzero exit status or on exceptions (e.g., missing environment variables or subprocess errors). Note: this function requires sudo privileges to succeed.
    """
    try:
        username = _get_current_username()
        print(f"Enabling lingering for user {username}...")
        result = subprocess.run(
            ["sudo", "loginctl", "enable-linger", username],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("Lingering enabled successfully")
            return True
        else:
            print(f"Error enabling lingering: {result.stderr}")
            return False
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        print(f"Error enabling lingering: {e}")
        return False


def start_service():
    """Start the systemd user service.

    Returns:
        bool: True if successful, False otherwise.
    """
    if SYSTEMCTL_PATH is None:
        print("systemctl not available on this system")
        return False
    try:
        subprocess.run(
            [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "start", SERVICE_NAME], check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error starting service: {e}")
        return False
    except OSError as e:
        print(f"Error: {e}")
        return False


def show_service_status():
    """
    Print the systemd user service status for the configured SERVICE_NAME.

    Runs `systemctl --user status <SERVICE_NAME>` and prints the command output to stdout.

    Returns:
        bool: True if the status command was executed and output printed; False if the command could not be run due to an OS or subprocess error.
    """
    if SYSTEMCTL_PATH is None:
        print("systemctl not available on this system")
        return False
    try:
        result = subprocess.run(
            [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "status", SERVICE_NAME],
            check=False,  # Don't raise an exception if the service is not active
            capture_output=True,
            text=True,
        )
        print("\nService Status:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        return result.returncode == 0
    except OSError as e:
        print(f"Error: {e}")
        return False


def install_service():
    """
    Install or update the BibleBot systemd user service.

    This is an interactive routine that ensures the user-level systemd service file exists
    and matches the current installation, creates or updates the service file if needed,
    reloads the user systemd daemon, and (optionally, with user consent) enables/starts/restarts
    the service and enables user lingering. The function prints prompts, progress messages,
    errors, and a final status summary to stdout.

    Behavior and side effects:
    - May create or overwrite the service file at the user systemd directory.
    - Reloads the systemd user daemon (daemon-reload).
    - May invoke `loginctl` (to check/enable lingering) and `sudo loginctl enable-linger` if the
      user agrees.
    - May run `systemctl --user enable|start|restart <SERVICE_NAME>` depending on user input.
    - Shows the service status after start/restart when applicable.

    This function is interactive and should be run in a terminal where user input is possible.

    Returns:
        bool: True on normal completion (including cases where the user declines optional actions);
              False if a fatal step failed (e.g., creating the service file or reloading the daemon).
    """
    if SYSTEMCTL_PATH is None:
        print("systemctl not available on this system")
        print("Cannot install systemd user service without systemctl")
        return False

    # Check if service already exists
    existing_service = read_service_file()
    service_path = get_user_service_path()

    # Check if the service needs to be updated
    update_needed, reason = service_needs_update()

    # Check if the service is already installed and if it needs updating
    if existing_service:
        print(f"A service file already exists at {service_path}")

        if update_needed:
            print(f"The service file needs to be updated: {reason}")
            if (
                not input("Do you want to update the service file? (y/n): ")
                .lower()
                .startswith("y")
            ):
                print("Service update cancelled.")
                print_service_commands()
                return True
        else:
            print(f"No update needed for the service file: {reason}")
    else:
        print(f"No service file found at {service_path}")
        print("A new service file will be created.")

    # Create or update service file if needed
    if not existing_service or update_needed:
        if not create_service_file():
            return False

        # Reload daemon
        if not reload_daemon():
            return False

        if existing_service:
            print("Service file updated successfully")
        else:
            print("Service file created successfully")

    # Check if loginctl is available
    loginctl_available = check_loginctl_available()
    if loginctl_available:
        # Check if user lingering is enabled
        lingering_enabled = check_lingering_enabled()
        if not lingering_enabled:
            print(
                "\nUser lingering is not enabled. This is required for the service to start automatically at boot."
            )
            print(
                "Lingering allows user services to run even when you're not logged in."
            )
            if (
                input(
                    "Do you want to enable lingering for your user? (requires sudo) (y/n): "
                )
                .lower()
                .startswith("y")
            ):
                enable_lingering()

    # Check if the service is already enabled
    service_enabled = is_service_enabled()
    if service_enabled:
        print("The service is already enabled to start at boot.")
    else:
        print("The service is not currently enabled to start at boot.")
        if (
            input("Do you want to enable the service to start at boot? (y/n): ")
            .lower()
            .startswith("y")
        ):
            try:
                subprocess.run(
                    [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "enable", SERVICE_NAME],
                    check=True,
                )
                print("Service enabled successfully")
                service_enabled = True
            except subprocess.CalledProcessError as e:
                print(f"Error enabling service: {e}")
            except OSError as e:
                print(f"Error: {e}")

    # Check if the service is already running
    service_active = is_service_active()
    if service_active:
        print("The service is already running.")
        if input("Do you want to restart the service? (y/n): ").lower().startswith("y"):
            try:
                subprocess.run(
                    [SYSTEMCTL_PATH, SYSTEMCTL_ARG_USER, "restart", SERVICE_NAME],
                    check=True,
                )
                print("Service restarted successfully")
                # Show service status
                show_service_status()
            except subprocess.CalledProcessError as e:
                print(f"Error restarting service: {e}")
            except OSError as e:
                print(f"Error: {e}")
    else:
        print("The service is not currently running.")
        if (
            input("Do you want to start the service now? (y/n): ")
            .lower()
            .startswith("y")
        ):
            if start_service():
                # Show service status
                show_service_status()
                print("Service started successfully")
            else:
                print("\nWarning: Failed to start the service. Please check the logs.")

    # Print a summary of the service status
    print("\nService Status Summary:")
    print(f"  Service File: {service_path}")
    print(f"  Enabled at Boot: {'Yes' if service_enabled else 'No'}")
    if loginctl_available:
        print(f"  User Lingering: {'Yes' if check_lingering_enabled() else 'No'}")
    print(f"  Currently Running: {'Yes' if is_service_active() else 'No'}")
    print("\nService Management Commands:")
    print_service_commands()

    return True
