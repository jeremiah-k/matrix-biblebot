#!/usr/bin/env python3
"""Command-line interface for BibleBot."""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Awaitable, Optional, TypeVar

from biblebot import __version__
from biblebot.auth import interactive_login, interactive_logout, load_credentials
from biblebot.bot import main as bot_main
from biblebot.constants.app import LOGGER_NAME
from biblebot.constants.config import (
    CONFIG_DIR,
    DEFAULT_CONFIG_FILENAME,
    E2EE_KEY_AVAILABLE,
)
from biblebot.constants.logging import DEFAULT_LOG_LEVEL, LOG_LEVELS
from biblebot.constants.messages import (
    CLI_ACTION_STORE_TRUE,
    CLI_ACTION_VERSION,
    CLI_ARG_CONFIG,
    CLI_ARG_LOG_LEVEL,
    CLI_ARG_VERSION,
    CLI_ARG_YES_LONG,
    CLI_ARG_YES_SHORT,
    CLI_DESCRIPTION,
    CLI_HELP_CONFIG,
    CLI_HELP_LOG_LEVEL,
    CLI_HELP_YES,
    CMD_AUTH,
    CMD_CHECK,
    CMD_CONFIG,
    CMD_GENERATE,
    CMD_INSTALL,
    CMD_LOGIN,
    CMD_LOGOUT,
    CMD_SERVICE,
    CMD_STATUS,
    MSG_CONFIG_EXISTS,
    MSG_DELETE_EXISTING,
    MSG_GENERATED_CONFIG,
    MSG_NO_CONFIG_PROMPT,
    SUCCESS_CONFIG_GENERATED,
)
from biblebot.log_utils import configure_logging, get_logger
from biblebot.tools import copy_sample_config_to

# Configure logging
logger = logging.getLogger(LOGGER_NAME)


# Wrapper to ease testing (tests can patch biblebot.cli.run_async)
T = TypeVar("T")


def run_async(coro: Awaitable[T]) -> T:
    """
    Run an asyncio coroutine to completion using asyncio.run and return its result.

    Parameters:
        coro: An awaitable coroutine to execute.

    Returns:
        The result returned by the coroutine.

    Notes:
        Exceptions raised by the coroutine are propagated to the caller.
    """
    return asyncio.run(coro)


def get_default_config_path() -> Path:
    """
    Return the default configuration file path used by the CLI.

    The path is constructed by joining the module CONFIG_DIR with DEFAULT_CONFIG_FILENAME.

    Returns:
        pathlib.Path: Full path to the default configuration file.
    """
    return CONFIG_DIR / DEFAULT_CONFIG_FILENAME


def detect_configuration_state() -> tuple[str, str, Optional[dict]]:
    """
    Determine the CLI's current configuration and authentication state.

    Returns a tuple (state, message, config) where:
    - state (str): One of:
        - "setup": no valid config file found; user should run configuration setup.
        - "auth": config exists but credentials are missing or invalid; user should authenticate.
        - "ready_legacy": a legacy MATRIX_ACCESS_TOKEN environment token is present (legacy auth, E2EE not supported); user may migrate to modern auth.
        - "ready": valid config and credentials are present; the bot can be started.
    - message (str): Human-facing explanation of the detected condition and suggested next steps.
    - config (dict|None): Loaded configuration dictionary when available, otherwise None.

    Errors encountered while loading or validating the configuration or credentials are not raised; they are mapped to an appropriate state ("setup" or "auth") with an explanatory message.
    """
    config_path = get_default_config_path()
    credentials_path = CONFIG_DIR / "credentials.json"

    # Check if config file exists
    if not config_path.exists():
        return "setup", "No configuration found. Setup is required.", None

    # Try to load and validate config
    try:
        from biblebot import bot

        config = bot.load_config(str(config_path))
        if not config:
            return "setup", "Invalid configuration. Setup is required.", None
    except (ImportError, ValueError, KeyError, TypeError, OSError) as e:
        return "setup", f"Configuration error: {e}", None

    # Check for proper authentication (credentials.json from auth flow)
    if not credentials_path.exists():
        # Check for legacy environment token (deprecated)
        from biblebot.constants.config import ENV_MATRIX_ACCESS_TOKEN

        if os.getenv(ENV_MATRIX_ACCESS_TOKEN):
            return (
                "ready_legacy",
                "Bot configured with legacy access token (E2EE not supported). Consider migrating to 'biblebot auth login'.",
                config,
            )
        return (
            "auth",
            "Configuration found but authentication required. Use 'biblebot auth login'.",
            config,
        )

    # Verify credentials are valid
    try:
        creds = load_credentials()
        if not creds:
            return (
                "auth",
                "Invalid credentials found. Re-authentication required.",
                config,
            )
    except (OSError, ValueError, TypeError):
        return "auth", "Cannot load credentials. Re-authentication required.", config

    return "ready", "Bot is configured and ready to start.", config


def generate_config(config_path: Path | str) -> bool:
    """
    Create a sample configuration file at config_path by copying the bundled template.

    If the target file already exists this function prints guidance and returns False.
    Otherwise it ensures the target directory exists, copies the sample config into
    place, sets restrictive file permissions (owner read/write only, mode 0o600),
    prints next-step instructions, and returns True.

    Parameters:
        config_path (str or pathlib.Path): Destination path for the generated config.

    Returns:
        bool: True if a new config file was created; False if the file already existed.
    """
    config_path = Path(config_path)
    config_dir = config_path.parent

    if config_path.exists():
        print(MSG_CONFIG_EXISTS)
        print(f"  {config_path}")
        print(MSG_DELETE_EXISTING)
        print("Otherwise, edit the current file in place.")
        return False

    config_dir.mkdir(parents=True, exist_ok=True)

    copy_sample_config_to(str(config_path))

    # Set restrictive permissions (readable/writable by owner only; ignore on platforms that don't support it)
    try:
        os.chmod(config_path, 0o600)
    except (AttributeError, NotImplementedError, OSError):
        pass

    print(MSG_GENERATED_CONFIG.format(config_path))
    print()
    print("📝 Please edit the configuration file with your Matrix server details.")
    print("🔑 Then run 'biblebot auth login' to authenticate.")
    print(SUCCESS_CONFIG_GENERATED)
    return True


def interactive_main():
    """
    Run an interactive CLI startup flow that ensures a valid configuration and authentication are present, then launches the bot.

    This orchestrates the user-facing startup paths detected by detect_configuration_state():
    - "setup": creates a sample configuration file and prints next steps.
    - "auth": launches an interactive Matrix login (skipped in CI/test environments); on success, starts the bot.
    - "ready_legacy": starts the bot using a legacy access token (deprecated path).
    - "ready": starts the bot normally.

    Side effects:
    - May create or modify files on disk (configuration).
    - May launch an interactive login flow (unless running in CI/test).
    - May start the bot process (blocking until the bot exits).
    """

    def _run_bot(
        config_path: Path | str, legacy: bool = False, config: Optional[dict] = None
    ):
        """
        Start the BibleBot process using the provided configuration.

        This function ensures logging is configured (using the given preloaded `config` when supplied,
        or by attempting to load `config_path`), then imports and runs the bot entrypoint. If the
        bot module exposes `main_with_config`, it will be preferred and invoked with the already-loaded
        configuration to avoid re-reading the file. The call blocks until the bot exits.

        Parameters:
            config_path: Path to the configuration file (string or Path). Used when `config` is not supplied.
            legacy: If True, annotate startup as legacy mode (affects startup mode only).
            config: Optional preloaded configuration dictionary; when provided, it will be used to
                configure logging and passed to the bot entrypoint to prevent reloading the file.

        Side effects:
            - Configures application logging (from `config` when available, otherwise attempts to load
              config from `config_path` and falls back to default logging on load errors).
            - Imports and runs the BibleBot entrypoint (blocking).
            - Logs a message and returns on KeyboardInterrupt.
            - On startup failures (RuntimeError, ConnectionError, FileNotFoundError, OSError, ValueError,
              TypeError) the function logs the error and exits the process with status code 1.
        """
        # Initialize logging first
        if config is None:
            try:
                from biblebot.bot import load_config

                # Load config without logging message to avoid duplicate logging
                # (config was already loaded in detect_configuration_state)
                config = load_config(config_path, log_loading=False)
                configure_logging(config)
            except (OSError, ValueError, TypeError):
                # If config loading fails, use default logging
                configure_logging(None)
        else:
            # Use provided config
            configure_logging(config)

        logger = get_logger(LOGGER_NAME, force=True)

        mode = " (legacy mode)" if legacy else ""
        logger.info(f"Starting Matrix BibleBot{mode}...")

        try:
            # Import bot module after logging is configured
            from biblebot import bot

            # If we successfully loaded config above, pass it to avoid duplicate loading
            if config is not None:
                main_with_config = getattr(bot, "main_with_config", None)
                if main_with_config:
                    run_async(main_with_config(str(config_path), config))
                else:
                    run_async(bot_main(str(config_path)))
            else:
                run_async(bot_main(str(config_path)))
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
        except (RuntimeError, ConnectionError, FileNotFoundError):
            logger.exception("Bot failed to start")
            sys.exit(1)
        except (OSError, ValueError, TypeError) as e:
            logger.exception(f"Unexpected error starting bot: {type(e).__name__}")
            sys.exit(1)

    # Initialize basic logging for CLI messages
    configure_logging(None)
    logger = get_logger(LOGGER_NAME)

    state, message, config = detect_configuration_state()

    logger.info("📖✝️ Matrix BibleBot ✝️")
    logger.info(f"Status: {message}")

    if state == "setup":
        logger.info("🔧 Setup Required - No configuration file found.")
        logger.info("Generating sample configuration file...")

        config_path = get_default_config_path()
        if generate_config(str(config_path)):
            logger.info("✅ Configuration file generated!")
            logger.info("📝 Next steps:")
            logger.info(f"   1. Edit {config_path}")
            logger.info("   2. Run 'biblebot' again to authenticate")
            return
        else:
            logger.error("❌ Failed to generate configuration file.")
            logger.error("You may need to run 'biblebot config generate' manually.")
            sys.exit(1)

    elif state == "auth":
        logger.info(
            "🔐 Authentication Required - Configuration found but Matrix credentials are missing."
        )
        logger.info(
            "The bot uses secure session-based authentication with encryption (E2EE) support."
        )

        # Check if we're in a test environment
        if (
            os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("TESTING")
            or os.environ.get("CI")
        ):
            logger.info("Test environment detected - skipping interactive login")
            return

        logger.info("🔑 Starting interactive login...")

        try:
            ok = run_async(interactive_login())
            if ok:
                logger.info("✅ Login completed! Starting bot...")
                # Auto-start the bot after successful login
                _run_bot(get_default_config_path(), config=config)
            else:
                logger.error("❌ Login failed.")
                sys.exit(1)
        except KeyboardInterrupt:
            logger.info("❌ Login cancelled.")
            return

    elif state == "ready_legacy":
        logger.warning("⚠️  Legacy Configuration Detected")
        logger.debug(
            "Bot is configured with a manual access token (deprecated, no E2EE support)."
        )
        logger.debug(
            "Consider running 'biblebot auth login' to upgrade to modern authentication."
        )
        logger.info("Starting bot with legacy token...")
        _run_bot(get_default_config_path(), legacy=True, config=config)

    elif state == "ready":
        logger.info("✅ Bot Ready - Configuration and credentials are valid.")
        logger.info("Starting bot...")
        _run_bot(get_default_config_path(), config=config)


def create_parser():
    """
    Create the CLI argument parser and subparsers used by the program.

    Builds the top-level argparse.ArgumentParser with global options (config path, log level, version, and a yes/force flag),
    and the following subcommand groups with their actions:

    - config: "generate" (create sample config) and "check" (validate config).
    - auth: "login" (interactive or non-interactive Matrix login), "logout" (remove credentials and E2EE state),
      and "status" (show auth and E2EE status).
      - The "login" action accepts optional --homeserver, --username, and --password; when any of these are provided,
        the other two are required for a non-interactive login attempt.
    - service: "install" (install or update per-user systemd service).

    Returns:
        tuple: (parser, config_parser, auth_parser, service_parser) where each element is an argparse parser
        for the corresponding command namespace.
    """
    default_config_path = get_default_config_path()

    # Main parser
    parser = argparse.ArgumentParser(
        description=CLI_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  biblebot                          # Run the bot
  biblebot config generate          # Generate sample config file
  biblebot config check             # Validate configuration file
  biblebot auth login               # Interactive login to Matrix
  biblebot auth logout              # Logout and clear credentials
  biblebot auth status              # Show authentication & E2EE status
  biblebot service install          # Install systemd service
        """,
    )

    # Global arguments
    parser.add_argument(
        CLI_ARG_CONFIG,
        default=str(default_config_path),
        help=CLI_HELP_CONFIG.format(default_config_path),
    )
    parser.add_argument(
        CLI_ARG_LOG_LEVEL,
        choices=LOG_LEVELS,
        default=DEFAULT_LOG_LEVEL,
        help=CLI_HELP_LOG_LEVEL.format(DEFAULT_LOG_LEVEL),
    )
    parser.add_argument(
        CLI_ARG_VERSION, action=CLI_ACTION_VERSION, version=f"BibleBot {__version__}"
    )
    parser.add_argument(
        CLI_ARG_YES_SHORT,
        CLI_ARG_YES_LONG,
        action=CLI_ACTION_STORE_TRUE,
        help=CLI_HELP_YES,
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Config subcommands
    config_parser = subparsers.add_parser(CMD_CONFIG, help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_action")

    config_subparsers.add_parser(CMD_GENERATE, help="Generate sample config file")
    config_subparsers.add_parser(CMD_CHECK, help="Validate configuration file")

    # Auth subcommands
    auth_parser = subparsers.add_parser(CMD_AUTH, help="Authentication management")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_action")

    # Login subcommand with optional arguments
    login_parser = auth_subparsers.add_parser(
        CMD_LOGIN, help="Interactive login to Matrix and save credentials"
    )
    login_parser.add_argument(
        "--homeserver",
        help="Matrix homeserver URL (e.g., https://matrix.org). If provided, --username and --password are also required.",
    )
    login_parser.add_argument(
        "--username",
        help="Matrix username (with or without @ and :server). If provided, --homeserver and --password are also required.",
    )
    login_parser.add_argument(
        "--password",
        metavar="PWD",
        help="Matrix password (can be empty). If provided, --homeserver and --username are also required. For security, prefer interactive mode.",
    )

    auth_subparsers.add_parser(
        CMD_LOGOUT, help="Logout and remove credentials and E2EE store"
    )
    auth_subparsers.add_parser(CMD_STATUS, help="Show authentication and E2EE status")

    # Service subcommands
    service_parser = subparsers.add_parser(CMD_SERVICE, help="Service management")
    service_subparsers = service_parser.add_subparsers(dest="service_action")

    service_subparsers.add_parser(
        CMD_INSTALL, help="Install or update systemd user service"
    )

    return parser, config_parser, auth_parser, service_parser


def main():
    """
    Entry point for the BibleBot command-line interface.

    Runs either an interactive guided startup flow (when invoked with no CLI arguments)
    or a modern grouped command dispatcher (when subcommands/flags are supplied).

    Behavior summary:
    - Interactive mode (no args): performs setup/login/run flow that can generate a sample
      config, prompt for authentication, or start the bot depending on current state.
    - Subcommands:
      - config generate: create a starter configuration file at the given --config path.
      - config check: validate an existing configuration file and print summary info
        (Matrix room count, configured API keys, E2EE support).
      - auth login [--homeserver --username --password]: perform interactive or
        non-interactive Matrix login and save credentials.
      - auth logout: remove stored credentials and E2EE state.
      - auth status: print authentication and E2EE status.
      - service install: install or update the per-user systemd service.

    Notes:
    - The default config path is used when --config is not provided.
    - --log-level controls logging verbosity.
    - The function may create files (sample config), install a service, modify stored
      credentials/E2EE data, or start the bot process. It also exits the process with
      appropriate status codes for command errors, validation failures, or runtime errors.
    """
    # If no arguments provided, use interactive mode
    if len(sys.argv) == 1:
        interactive_main()
        return

    parser, config_parser, auth_parser, service_parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    log_level = getattr(logging, args.log_level.upper())
    configure_logging(None)
    get_logger(LOGGER_NAME, force=True).setLevel(log_level)

    # Handle modern grouped commands
    if args.command == CMD_CONFIG:
        if args.config_action == CMD_GENERATE:
            generate_config(args.config)
            return
        elif args.config_action == CMD_CHECK:
            from biblebot.bot import load_config

            config = load_config(args.config)
            if not config:
                # load_config already logs the specific error.
                sys.exit(1)

            try:
                print("✓ Configuration file is valid")
                print(f"  Config file: {args.config}")
                rooms = (config.get("matrix", {}) or {}).get("room_ids") or config.get(
                    "matrix_room_ids", []
                )
                print(f"  Matrix rooms: {len(rooms or [])}")
                from biblebot.bot import load_environment

                _, api_keys = load_environment(config, args.config)
                print(
                    f"  API keys configured: {len([k for k, v in api_keys.items() if v])}"
                )

                # Check E2EE status
                from biblebot.auth import check_e2ee_status

                e2ee_status = check_e2ee_status()
                print(
                    f"  E2EE support: {'✓' if e2ee_status[E2EE_KEY_AVAILABLE] else '✗'}"
                )

            except (KeyError, ValueError, TypeError) as e:
                print(f"✗ Configuration validation failed: {e}")
                sys.exit(1)
            return
        else:
            config_parser.print_help()
            sys.exit(2)

    elif args.command == CMD_AUTH:
        if args.auth_action == CMD_LOGIN:
            # Extract arguments if provided
            homeserver = getattr(args, "homeserver", None)
            username = getattr(args, "username", None)
            password = getattr(args, "password", None)

            # Validate argument combinations
            provided_params = [
                p for p in [homeserver, username, password] if p is not None
            ]

            if len(provided_params) > 0 and len(provided_params) < 3:
                # Some but not all parameters provided - show error
                missing_params = []
                if homeserver is None:
                    missing_params.append("--homeserver")
                if username is None:
                    missing_params.append("--username")
                if password is None:
                    missing_params.append("--password")

                print(
                    "❌ Error: All authentication parameters are required when using command-line options."
                )
                print(f"   Missing: {', '.join(missing_params)}")
                print()
                print("💡 Options:")
                print("   • For secure interactive authentication: biblebot auth login")
                print("   • For automated authentication: provide all three parameters")
                print()
                print(
                    "⚠️  Security Note: Command-line passwords may be visible in process lists and shell history."
                )
                print("   Interactive mode is recommended for manual use.")
                sys.exit(1)
            elif len(provided_params) == 3:
                # All parameters provided - validate required non-empty fields
                if not homeserver or not homeserver.strip():
                    print(
                        "❌ Error: --homeserver must be non-empty for non-interactive login."
                    )
                    sys.exit(1)
                if not username or not username.strip():
                    print(
                        "❌ Error: --username must be non-empty for non-interactive login."
                    )
                    sys.exit(1)
                # Password may be empty (some flows may prompt)

            ok = run_async(interactive_login(homeserver, username, password))
            sys.exit(0 if ok else 1)
        elif args.auth_action == CMD_LOGOUT:
            ok = run_async(interactive_logout())
            sys.exit(0 if ok else 1)
        elif args.auth_action == CMD_STATUS:
            from biblebot.auth import print_e2ee_status

            # Show authentication status
            creds = load_credentials()
            if creds:
                print("🔑 Authentication Status: ✓ Logged in")
                print(f"  User: {creds.user_id}")
                print(f"  Homeserver: {creds.homeserver}")
                print(f"  Device: {creds.device_id}")
            else:
                print("🔑 Authentication Status: ✗ Not logged in")
                print("  Run 'biblebot auth login' to authenticate")

            # Show E2EE status
            print_e2ee_status()
            return
        else:
            auth_parser.print_help()
            sys.exit(2)

    elif args.command == CMD_SERVICE:
        if args.service_action == CMD_INSTALL:
            from biblebot.setup_utils import install_service

            install_service()
            return
        else:
            service_parser.print_help()
            sys.exit(2)

    # Check if config file exists - always required for bot operation
    if not os.path.exists(args.config):
        logging.warning(f"Config file not found: {args.config}")
        # Offer to generate at this location
        if args.yes:
            resp = "y"
        else:
            try:
                resp = input(MSG_NO_CONFIG_PROMPT).strip().lower()
            except (EOFError, KeyboardInterrupt):
                resp = "n"
        if resp.startswith("y"):
            created = generate_config(args.config)
            if created:
                # Exit after successful generation so the user can edit the new files.
                sys.exit(0)
            else:
                # Generation failed (e.g., permissions error).
                # generate_config() already printed a message.
                sys.exit(1)
        else:
            logging.info("Tip: run 'biblebot config generate' to create starter files.")
            sys.exit(1)

    # Run the bot
    try:
        run_async(bot_main(args.config))
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except FileNotFoundError:
        logging.exception(
            f"Configuration file not found: {args.config}. "
            "Run 'biblebot config generate' to create one."
        )
        sys.exit(1)
    except (RuntimeError, ConnectionError):
        logging.exception("Error running bot")
        sys.exit(1)
    except (ValueError, TypeError, OSError, ImportError) as e:
        logging.exception(f"Unexpected error running bot: {type(e).__name__}")
        sys.exit(1)


if __name__ == "__main__":
    main()
