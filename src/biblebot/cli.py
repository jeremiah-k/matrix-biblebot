#!/usr/bin/env python3
"""Command-line interface for BibleBot."""

import argparse
import asyncio
import logging
import os
import shutil
import sys
import warnings

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
from .tools import get_sample_config_path

# Configure logging
logger = logging.getLogger(LOGGER_NAME)


# Wrapper to ease testing (tests can patch biblebot.cli.run_async)
def run_async(coro):
    return asyncio.run(coro)


def get_default_config_path():
    """Get the default config path in the user's home directory."""
    return CONFIG_DIR / DEFAULT_CONFIG_FILENAME


def detect_configuration_state():
    """Detect the current configuration state and return appropriate action."""
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
    """Generate a sample config file at the specified path."""
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
    """Interactive main function that guides users through setup/auth/start."""

    def _run_bot(config_path: str, legacy: bool = False):
        """Helper to run the bot and handle common exceptions."""
        mode = " (legacy mode)" if legacy else ""
        print(f"🚀 Starting Matrix BibleBot{mode}...")
        try:
            run_async(bot_main(str(config_path)))
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user.")
        except (RuntimeError, ConnectionError, FileNotFoundError) as e:
            print(f"\n❌ Bot failed to start: {e}")
            print("Check your configuration and try again.")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print("Check your configuration and try again.")
            sys.exit(1)

    state, message = detect_configuration_state()

    print("🤖 Matrix BibleBot")
    print(f"Status: {message}")
    print()

    if state == "setup":
        print("🔧 Setup Required")
        print("The bot needs to be configured before it can run.")
        print()
        try:
            response = (
                input("Would you like to generate sample configuration now? [Y/n]: ")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.")
            return
        if response in ("", "y", "yes"):
            config_path = get_default_config_path()
            if generate_config(str(config_path)):
                print()
                print("✅ Configuration file generated!")
                print("📝 Next steps:")
                print(f"   1. Edit {config_path}")
                print("   2. Run 'biblebot' again to authenticate")
            return
        else:
            print("Setup cancelled. Run 'biblebot config generate' when ready.")
            return

    elif state == "auth":
        print("🔐 Authentication Required")
        print("Configuration found but Matrix credentials are missing.")
        print()
        print("The bot uses secure session-based authentication that supports E2EE.")
        print("Manual access tokens are deprecated and don't support E2EE.")
        print()
        try:
            response = input("Would you like to login now? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAuthentication cancelled.")
            return
        if response in ("", "y", "yes"):
            print("🔑 Starting interactive login...")
            try:
                ok = run_async(interactive_login())
                if ok:
                    print("✅ Login completed! Run 'biblebot' again to start the bot.")
                else:
                    print("❌ Login failed.")
            except KeyboardInterrupt:
                print("\n❌ Login cancelled.")
            return
        else:
            print("Authentication cancelled. Use 'biblebot auth login' when ready.")
            return

    elif state == "ready_legacy":
        print("⚠️  Legacy Configuration Detected")
        print("Bot is configured with a manual access token.")
        print("This method is deprecated and does NOT support E2EE.")
        print()
        print("Consider migrating to modern authentication:")
        print("  1. Run 'biblebot auth login' to use secure session-based auth")
        print("  2. This enables E2EE support and better security")
        print()
        try:
            response = input("Start with legacy token anyway? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        if response in ("y", "yes"):
            _run_bot(get_default_config_path(), legacy=True)
        else:
            print(
                "Consider running 'biblebot auth login' to upgrade to modern authentication."
            )

    elif state == "ready":
        print("✅ Bot Ready")
        print("Configuration and credentials are valid.")
        print()
        try:
            response = (
                input("Would you like to start the bot now? [Y/n]: ").strip().lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        if response in ("", "y", "yes"):
            _run_bot(get_default_config_path())
        else:
            print(
                "Bot not started. Use 'biblebot' to start or 'biblebot --help' for options."
            )


def main():
    """Run the BibleBot CLI with modern grouped commands."""
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

    auth_subparsers.add_parser(
        "login", help="Interactive login to Matrix and save credentials"
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
            ok = run_async(interactive_login())
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
    except (RuntimeError, ConnectionError, FileNotFoundError) as e:
        logging.error(f"Error running bot: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error running bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
