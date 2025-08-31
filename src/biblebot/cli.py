#!/usr/bin/env python3
"""Command-line interface for BibleBot."""

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .auth import interactive_login, interactive_logout
from .bot import main as bot_main
from .tools import get_sample_config_path, get_sample_env_path

# Configure logging
logger = logging.getLogger("BibleBot")


def get_default_config_path():
    """Get the default config path in the user's home directory."""
    config_dir = Path.home() / ".config" / "matrix-biblebot"
    return config_dir / "config.yaml"


def generate_config(config_path):
    """Generate a sample config file at the specified path."""
    config_dir = os.path.dirname(config_path)
    env_path = os.path.join(config_dir, ".env")

    if os.path.exists(config_path) or os.path.exists(env_path):
        print("A config or .env file already exists at:")
        if os.path.exists(config_path):
            print(f"  {config_path}")
        if os.path.exists(env_path):
            print(f"  {env_path}")
        print("If you want to regenerate them, delete the existing files first.")
        print("Otherwise, edit the current files in place.")
        return False

    os.makedirs(config_dir, exist_ok=True)

    sample_config_path = get_sample_config_path()
    sample_env_path = get_sample_env_path()

    shutil.copy2(sample_config_path, config_path)
    shutil.copy2(sample_env_path, env_path)

    print(f"Generated sample config file at: {config_path}")
    print(f"Generated sample .env file at: {env_path}")
    print("Please edit these files with your Matrix credentials and API keys.")
    return True


def main():
    """Run the BibleBot CLI with modern grouped commands."""
    default_config_path = get_default_config_path()

    # Main parser
    parser = argparse.ArgumentParser(
        description="BibleBot for Matrix - A Bible verse bot with E2EE support",
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
        "--config",
        default=str(default_config_path),
        help=f"Path to config file (default: {default_config_path})",
    )
    parser.add_argument(
        "--log-level",
        choices=["error", "warning", "info", "debug"],
        default="info",
        help="Set logging level (default: info)",
    )
    parser.add_argument(
        "--version", action="version", version=f"BibleBot {__version__}"
    )

    # Legacy flags for backward compatibility (deprecated)
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help=argparse.SUPPRESS,  # Hide from help but keep functional
    )
    parser.add_argument(
        "--install-service",
        action="store_true",
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
    import warnings

    if args.generate_config:
        warnings.warn(
            "--generate-config is deprecated. Use 'biblebot config generate' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        generate_config(args.config)
        return

    if args.install_service:
        warnings.warn(
            "--install-service is deprecated. Use 'biblebot service install' instead.",
            DeprecationWarning,
            stacklevel=2,
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
        ok = asyncio.run(interactive_login())
        sys.exit(0 if ok else 1)

    if args.auth_logout:
        warnings.warn(
            "--auth-logout is deprecated. Use 'biblebot auth logout' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        ok = asyncio.run(interactive_logout())
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

                _, api_keys = load_environment(args.config)
                print(
                    f"  API keys configured: {len([k for k, v in api_keys.items() if v])}"
                )

                # Check E2EE status
                from .auth import check_e2ee_status

                e2ee_status = check_e2ee_status()
                print(f"  E2EE support: {'✓' if e2ee_status['available'] else '✗'}")

            except Exception as e:
                print(f"✗ Configuration validation failed: {e}")
                sys.exit(1)
            return
        else:
            config_parser.print_help()
            return

    elif args.command == "auth":
        if args.auth_action == "login":
            ok = asyncio.run(interactive_login())
            sys.exit(0 if ok else 1)
        elif args.auth_action == "logout":
            ok = asyncio.run(interactive_logout())
            sys.exit(0 if ok else 1)
        elif args.auth_action == "status":
            from .auth import load_credentials, print_e2ee_status

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

    # Check if config file exists (unless credentials exist for headless use)
    creds = load_credentials()
    if not os.path.exists(args.config) and not creds:
        logging.warning(f"Config file not found: {args.config}")
        # Offer to generate at this location
        try:
            resp = (
                input(
                    "No config found. Generate sample config and .env here now? [y/N]: "
                )
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            resp = "n"
        if resp.startswith("y"):
            created = generate_config(args.config)
            if not created:
                sys.exit(1)
        else:
            logging.info("Tip: run 'biblebot config generate' to create starter files.")
            sys.exit(1)

    # Run the bot
    try:
        asyncio.run(bot_main(args.config))
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Error running bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
