# Development Guide

## Requirements

- **Python 3.12 or newer** (3.12–3.14 are tested in CI)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip + venv
- Docker, if you want to run the container build locally

## Quick Start

1. **Clone the repository:**

   ```bash
   git clone https://github.com/jeremiah-k/matrix-biblebot.git
   cd matrix-biblebot
   ```

2. **Set up development environment:**

   ```bash
   uv venv venv --python 3.12
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install in development mode:**

   ```bash
   pip install -e '.[e2e,test]'
   # Windows PowerShell: pip install -e ".[e2e,test]"
   ```

4. **Run tests:**
   ```bash
   pytest
   ```

## Project Structure

```text
matrix-biblebot/
├── src/biblebot/           # Main package
│   ├── __init__.py         # Version single-source-of-truth
│   ├── __main__.py         # Entry point for python -m biblebot
│   ├── auth.py             # Matrix authentication, credentials, E2EE setup
│   ├── bot.py              # BibleBot class: Matrix event loop and handlers
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Config file loading helpers
│   ├── formatting.py       # Passage text formatting helpers
│   ├── log_utils.py        # Logging configuration
│   ├── messaging.py        # Send-error classification and retry helpers
│   ├── passages.py         # Passage retrieval: API clients, cache, dispatch
│   ├── paths.py            # Runtime path resolution (XDG / BIBLEBOT_HOME)
│   ├── protocols.py        # BotClient structural type for the Matrix client
│   ├── rooms.py            # Room identifier resolution helpers
│   ├── service.py          # systemd unit planning/rendering
│   ├── setup_utils.py      # `biblebot service install` implementation
│   ├── triggers.py         # Scripture-reference detection
│   ├── update_check.py     # Startup release check
│   ├── validation.py       # Book-name validation/normalization
│   ├── constants/          # Configuration constants
│   └── tools/              # Packaged assets (sample config, service template)
├── tests/                  # Test suite (see docs/dev/TESTING.md)
├── docs/                   # User documentation
│   └── dev/                # Contributor documentation
├── main.py                 # Legacy entry point
└── pyproject.toml          # Package metadata, dependencies, tool config
```

Package management is fully defined by `pyproject.toml`; there is no
`setup.py` or `requirements*.txt`.

## Core Components

### Bot Class (`src/biblebot/bot.py`)

The main `BibleBot` class handles:

- Matrix event processing (`on_room_message`)
- Scripture command orchestration (`handle_scripture_command`)
- Message formatting/splitting delegation
- E2EE decryption-failure recovery (room-key request fallback)

Passage retrieval itself lives in `passages.py`; the bot only orchestrates.

Key methods:

- `start()` - Initialize the client, join rooms, start syncing
- `on_room_message(room, event)` - Entry point for incoming messages
- `handle_scripture_command(room_id, passage, translation, event)` - Fetch a passage and deliver it
- `_send_message_parts(room_id, parts, reference)` - Delivery with rate-limit retry; returns a non-retriable nio `ErrorResponse`, or raises `MessageSendError` for transport failures
- `_handle_failed_send(room_id, error)` - Report delivery failures to users without attempting impossible notices

### CLI Interface (`src/biblebot/cli.py`)

Provides command-line interface with subcommands:

- `config generate/check` - Configuration management
- `auth login/logout/status/cross-sign` - Authentication and device identity
- `service install` - Systemd user service setup

### Passage Retrieval (`src/biblebot/passages.py`)

Everything between a scripture reference and its text:

- `get_bible_text(passage, translation, ...)` - Cache-aware dispatch
- `get_esv_text` / `get_kjv_text` - Translation API backends
- `make_api_request` - Shared aiohttp GET helper
- LRU/TTL passage cache (`_cache_get` / `_cache_set`)

### Messaging Helpers (`src/biblebot/messaging.py`)

Pure functions used by the send path:

- `is_error_response` / `is_rate_limit_response` - nio response inspection
- `response_retry_delay_seconds` - Backoff computation with jitter
- `classify_send_failure` - Map an ErrorResponse to a user-facing failure kind

### Authentication (`src/biblebot/auth.py`)

Handles Matrix authentication:

- Modern credential-based auth with E2EE support
- Legacy access token fallback
- Secure credential storage
- Device management and cross-signing bootstrap

### Runtime Paths (`src/biblebot/paths.py`)

Single authority for where files live:

- `BIBLEBOT_HOME` places everything under one directory (Docker model)
- Otherwise: configuration under the XDG config home, runtime state
  (E2EE store, logs) under the XDG state home
- Automatic migration of legacy single-directory layouts on first access

See [Configuration Guide](../CONFIGURATION.md#runtime-state-location-e2ee-store-and-logs).

## Development Workflow

### Making Changes

1. Create a feature branch from `main`
2. Make changes with tests
3. Run the full suite before pushing
4. Open a pull request; CI runs the suite on Python 3.12–3.14 plus Docker validation

### Testing

```bash
pytest                                      # All tests
pytest --cov=biblebot                       # With coverage
pytest tests/test_bot.py                    # Specific file
pytest tests/test_messaging.py -q           # Quiet, one module
```

The E2EE dependency mocking strategy and test conventions are documented in
the [Testing Guide](dev/TESTING.md) — read it before writing tests that touch
Matrix client interactions.

## Linting and Formatting

This project uses [Trunk](https://trunk.io) as the lint/format umbrella
(ruff, black, isort, bandit, checkov, and more):

```bash
trunk check            # Report
trunk check --fix      # Autofix what is fixable
```

CI runs `docker-validate` and the full test suite on every pull request.

## Documentation

User-facing documentation lives in `docs/`. When you change behavior that
affects configuration, paths, or troubleshooting steps, update the relevant
guide in the same PR.
