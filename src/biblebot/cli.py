#!/usr/bin/env python3
"""Command-line interface for BibleBot."""

import argparse
import asyncio
import logging
import os
import shutil
import sys
import warnings
from typing import Awaitable, TypeVar

from . import __version__
from .auth import interactive_login, interactive_logout, load_credentials
from .bot import main as bot_main
from .constants import (
    CLI_ACTION_STORE_TRUE,
    CLI_ACTION_VERSION,
    CLI_ARG_CONFIG,
    CLI_ARG_GENERATE_CONFIG,
    CLI_ARG_INSTALL_SERVICE,
    CLI_ARG_LOG_LEVEL,
    CLI_ARG_VERSION,
    CLI_ARG_YES_LONG,
    CLI_ARG_YES_SHORT,
    CLI_DESCRIPTION,
    CLI_HELP_CONFIG,
    CLI_HELP_LOG_LEVEL,
    CLI_HELP_YES,
    CONFIG_DIR,
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_LOG_LEVEL,
    E2EE_KEY_AVAILABLE,
    LOG_LEVELS,
    LOGGER_NAME,
    MSG_CONFIG_EXISTS,
    MSG_DELETE_EXISTING,
    MSG_GENERATED_CONFIG,
    MSG_NO_CONFIG_PROMPT,
    SUCCESS_CONFIG_GENERATED,
)
from .log_utils import configure_logging, get_logger
from .tools import get_sample_config_path

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


def get_default_config_path():
    """
    Return the default configuration file path used by the CLI.

    The path is constructed by joining the module CONFIG_DIR with DEFAULT_CONFIG_FILENAME.

    Returns:
        pathlib.Path: Full path to the default configuration file.
    """
    return CONFIG_DIR / DEFAULT_CONFIG_FILENAME


def detect_configuration_state():
    """
    Determine the CLI's current configuration/authentication state.

    Returns a 2-tuple (state, message) where `state` is one of:
    - "setup": no valid config present; user should run configuration setup.
    - "auth": configuration exists but credentials are missing or invalid; user should authenticate.
    - "ready_legacy": a legacy MATRIX_ACCESS_TOKEN environment token is present (E2EE not supported); user may migrate to the modern auth flow.
    - "ready": configuration and credentials are present and valid; bot can be started.

    The accompanying `message` is a user-facing string describing the detected condition and recommended next steps. Errors encountered while loading or validating the configuration or credentials are mapped to the appropriate state ("setup" or "auth") with an explanatory message rather than being raised.
    """
    config_path = get_default_config_path()
    credentials_path = CONFIG_DIR / "credentials.json"

    # Check if config file exists
    if not config_path.exists():
        return "setup", "No configuration found. Setup is required."

    # Try to load and validate config
    try:
        from . import bot

        config = bot.load_config(str(config_path))
        if not config:
            return "setup", "Invalid configuration. Setup is required."
    except (ValueError, KeyError, TypeError, OSError) as e:
        return "setup", f"Configuration error: {e}"

    # Check for proper authentication (credentials.json from auth flow)
    if not credentials_path.exists():
        # Check for legacy environment token (deprecated)
        if os.getenv("MATRIX_ACCESS_TOKEN"):
            return (
                "ready_legacy",
                "Bot configured with legacy access token (E2EE not supported). Consider migrating to 'biblebot auth login'.",
            )
        return (
            "auth",
            "Configuration found but authentication required. Use 'biblebot auth login'.",
        )

    # Verify credentials are valid
    try:
        creds = load_credentials()
        if not creds:
            return "auth", "Invalid credentials found. Re-authentication required."
    except Exception:
        return "auth", "Cannot load credentials. Re-authentication required."

    return "ready", "Bot is configured and ready to start."


def generate_config(config_path):
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
    config_dir = os.path.dirname(config_path) or os.getcwd()

    if os.path.exists(config_path):
        print(MSG_CONFIG_EXISTS)
        print(f"  {config_path}")
        print(MSG_DELETE_EXISTING)
        print("Otherwise, edit the current file in place.")
        return False

    os.makedirs(config_dir, exist_ok=True)

    sample_config_path = get_sample_config_path()

    shutil.copy2(sample_config_path, config_path)

    # Set restrictive permissions (readable/writable by owner only)
    os.chmod(config_path, 0o600)

    print(MSG_GENERATED_CONFIG.format(config_path))
    print()
    print("📝 Please edit the configuration file with your Matrix server details.")
    print("🔑 Then run 'biblebot auth login' to authenticate.")
    print(SUCCESS_CONFIG_GENERATED)
    return True


def interactive_main():
    """
    Interactive CLI entry that guides the user through initial setup, authentication, and starting the bot.

    This function provides a streamlined UX:
    - If no config exists: generates sample config and exits with instructions
    - If config exists but no auth: automatically prompts for login, then starts bot
    - If config and auth exist: immediately starts the bot

    No unnecessary "Would you like to..." prompts - just does what the user expects.

    Side effects:
    - May create a configuration file on disk.
    - May launch the interactive login flow.
    - May start the bot by calling bot_main via run_async.
    - Uses proper logging instead of print statements.

    Returns:
        None
    """

    def _run_bot(config_path: str, legacy: bool = False):
        """
        Run the BibleBot process for the given configuration and handle common startup errors.

        Uses proper logging instead of print statements.
        """
        # Initialize logging first
        try:
            from .config import load_config

            config = load_config(config_path)
            configure_logging(config)
        except Exception:
            # If config loading fails, use default logging
            configure_logging(None)

        logger = get_logger("biblebot.cli")

        mode = " (legacy mode)" if legacy else ""
        logger.info(f"Starting Matrix BibleBot{mode}...")

        try:
            run_async(bot_main(str(config_path)))
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
        except (RuntimeError, ConnectionError, FileNotFoundError) as e:
            logger.error(f"Bot failed to start: {e}")
            logger.error("Check your configuration and try again.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error("Check your configuration and try again.")
            logger.exception("Unexpected error starting bot")
            sys.exit(1)

    def _get_user_input(prompt: str, cancellation_message: str = "Cancelled.") -> str:
        """
        Prompt the user for input, returning the trimmed, lowercased response or None if the user cancels.

        Reads a line from standard input using the provided prompt. Leading/trailing whitespace is removed
        and the result is converted to lowercase before being returned. If the user cancels input (Ctrl+C
        or EOF), prints the provided cancellation_message on its own line and returns None.

        Parameters:
            prompt: Text shown to the user when requesting input.
            cancellation_message: Message printed when input is cancelled (default: "Cancelled.").

        Returns:
            The user's input as a stripped, lowercase string, or None if input was cancelled.
        """
        try:
            return input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{cancellation_message}")
            return None

    # Initialize basic logging for CLI messages
    configure_logging(None)
    logger = get_logger("biblebot.cli")

    state, message = detect_configuration_state()

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
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING"):
            logger.info("Test environment detected - skipping interactive login")
            return

        logger.info("🔑 Starting interactive login...")

        try:
            ok = run_async(interactive_login())
            if ok:
                logger.info("✅ Login completed! Starting bot...")
                # Auto-start the bot after successful login
                _run_bot(get_default_config_path())
            else:
                logger.error("❌ Login failed.")
                sys.exit(1)
        except KeyboardInterrupt:
            logger.info("❌ Login cancelled.")
            return

    elif state == "ready_legacy":
        logger.warning("⚠️  Legacy Configuration Detected")
        logger.warning(
            "Bot is configured with a manual access token (deprecated, no E2EE support)."
        )
        logger.warning(
            "Consider running 'biblebot auth login' to upgrade to modern authentication."
        )
        logger.info("Starting bot with legacy token...")
        _run_bot(get_default_config_path(), legacy=True)

    elif state == "ready":
        logger.info("✅ Bot Ready - Configuration and credentials are valid.")
        logger.info("Starting bot...")
        _run_bot(get_default_config_path())


def main():
    """
    Run the BibleBot command-line interface.

    If invoked with no arguments, enters the interactive setup/run flow. When called with arguments, provides modern grouped subcommands:
    - config generate / validate: create a sample config or validate an existing config file.
    - auth login / logout / status: perform interactive Matrix login/logout and show authentication/E2EE status.
    - service install: install or update the per-user systemd service.

    Legacy, deprecated flags (--generate-config, --install-service, --auth-login, --auth-logout) are still accepted for backward compatibility and map to the corresponding modern commands while emitting deprecation warnings.

    Side effects:
    - May create files (sample config), install a service, modify credentials/E2EE state, or start the running bot.
    - May call sys.exit with non-zero codes on errors or after certain operations (e.g., failed validation, missing config, failed auth, or bot runtime errors).

    Logging is configured from the --log-level argument. The default config path is used when --config is not provided.
    """
    # If no arguments provided, use interactive mode
    if len(sys.argv) == 1:
        interactive_main()
        return

    default_config_path = get_default_config_path()

    # Main parser
    parser = argparse.ArgumentParser(
        description=CLI_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  biblebot                          # Run the bot
  biblebot config generate          # Generate sample config files
  biblebot auth login               # Interactive login to Matrix
  biblebot auth logout              # Logout and clear credentials
  biblebot service install          # Install systemd service

Legacy flags (deprecated):
  --auth-login, --auth-logout, --generate-config, --install-service
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

    # Legacy flags for backward compatibility (deprecated)
    parser.add_argument(
        CLI_ARG_GENERATE_CONFIG,
        action=CLI_ACTION_STORE_TRUE,
        help=argparse.SUPPRESS,  # Hide from help but keep functional
    )
    parser.add_argument(
        CLI_ARG_INSTALL_SERVICE,
        action=CLI_ACTION_STORE_TRUE,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--auth-login",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--auth-logout",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Config subcommands
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_action")

    config_subparsers.add_parser("generate", help="Generate sample config files")
    config_subparsers.add_parser("validate", help="Validate configuration file")

    # Auth subcommands
    auth_parser = subparsers.add_parser("auth", help="Authentication management")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_action")

    # Login subcommand with optional arguments
    login_parser = auth_subparsers.add_parser(
        "login", help="Interactive login to Matrix and save credentials"
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
        "logout", help="Logout and remove credentials and E2EE store"
    )
    auth_subparsers.add_parser("status", help="Show authentication and E2EE status")

    # Service subcommands
    service_parser = subparsers.add_parser("service", help="Service management")
    service_subparsers = service_parser.add_subparsers(dest="service_action")

    service_subparsers.add_parser(
        "install", help="Install or update systemd user service"
    )

    args = parser.parse_args()

    # Set up logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Handle legacy flags with deprecation warnings
    if args.generate_config:
        warnings.warn(
            "--generate-config is deprecated. Use 'biblebot config generate' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        logging.warning(
            "--generate-config is deprecated. Use 'biblebot config generate' instead."
        )
        generate_config(args.config)
        return

    if args.install_service:
        warnings.warn(
            "--install-service is deprecated. Use 'biblebot service install' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        logging.warning(
            "--install-service is deprecated. Use 'biblebot service install' instead."
        )
        from .setup_utils import install_service

        install_service()
        return

    if args.auth_login:
        warnings.warn(
            "--auth-login is deprecated. Use 'biblebot auth login' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        logging.warning(
            "--auth-login is deprecated. Use 'biblebot auth login' instead."
        )
        ok = run_async(interactive_login())
        sys.exit(0 if ok else 1)

    if args.auth_logout:
        warnings.warn(
            "--auth-logout is deprecated. Use 'biblebot auth logout' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        logging.warning(
            "--auth-logout is deprecated. Use 'biblebot auth logout' instead."
        )
        ok = run_async(interactive_logout())
        sys.exit(0 if ok else 1)

    # Handle modern grouped commands
    if args.command == "config":
        if args.config_action == "generate":
            generate_config(args.config)
            return
        elif args.config_action == "validate":
            from .bot import load_config

            config = load_config(args.config)
            if not config:
                # load_config already logs the specific error.
                sys.exit(1)

            try:
                print("✓ Configuration file is valid")
                print(f"  Config file: {args.config}")
                print(f"  Matrix rooms: {len(config.get('matrix_room_ids', []))}")
                from .bot import load_environment

                _, api_keys = load_environment(config, args.config)
                print(
                    f"  API keys configured: {len([k for k, v in api_keys.items() if v])}"
                )

                # Check E2EE status
                from .auth import check_e2ee_status

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
            return

    elif args.command == "auth":
        if args.auth_action == "login":
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
        elif args.auth_action == "logout":
            ok = run_async(interactive_logout())
            sys.exit(0 if ok else 1)
        elif args.auth_action == "status":
            from .auth import print_e2ee_status

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
            return

    elif args.command == "service":
        if args.service_action == "install":
            from .setup_utils import install_service

            install_service()
            return
        else:
            service_parser.print_help()
            return

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
        logging.error(f"Configuration file not found: {args.config}")
        logging.error(
            "Please check the path or generate a new config with 'biblebot config generate'."
        )
        sys.exit(1)
    except (RuntimeError, ConnectionError):
        logging.exception("Error running bot")
        sys.exit(1)
    except Exception:
        logging.exception("Unexpected error running bot")
        sys.exit(1)


if __name__ == "__main__":
    main()
