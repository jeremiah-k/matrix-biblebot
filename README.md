# Matrix BibleBot

A Matrix bot that fetches Bible verses and shares them in chat rooms. Simply send a Bible reference like "John 3:16" as a message and the bot will respond with the verse text.

## What it does

**Input:** `John 3:16 esv`
**Output:**

> For God so loved the world, that he gave his only Son, that whoever believes in him should not perish but have eternal life. - John 3:16 🕊️✝️

The bot supports both KJV (default) and ESV translations, works in encrypted rooms, and can split long passages into multiple messages.

## Quick Start

1. **Install the bot**

   ```bash
   pipx install matrix-biblebot
   ```

2. **Authenticate with Matrix**

   ```bash
   biblebot auth login
   ```

3. **Generate and edit config**

   ```bash
   biblebot config generate
   ```

   Then edit `~/.config/matrix-biblebot/config.yaml` to add your room IDs
   (or `$BIBLEBOT_HOME/config.yaml` if `BIBLEBOT_HOME` is set).

4. **Run the bot**

   ```bash
   biblebot
   ```

5. **Invite the bot to your Matrix rooms** and start sending Bible references!

## Features

- 📖 **Bible Translations**: KJV (default) and ESV support
- 🔒 **End-to-End Encryption**: Works in encrypted Matrix rooms
- ✂️ **Smart Message Splitting**: Long passages split intelligently
- 🚀 **Production Ready**: Rate limiting, error handling, systemd service
- 🎯 **Direct-Only Triggers**: Responds only when the entire message is a scripture reference

## Installation

### Recommended: pipx

```bash
# Basic installation
pipx install matrix-biblebot

# With end-to-end encryption support
pipx install 'matrix-biblebot[e2e]'
# Windows PowerShell (no native E2EE): pipx install matrix-biblebot
```

### Alternative: pip

```bash
pip install matrix-biblebot
# or with E2EE support
pip install 'matrix-biblebot[e2e]'
# Windows PowerShell (no native E2EE): pip install matrix-biblebot
```

Native Windows installs do not currently support E2EE (`python-olm`/`matrix-nio[e2e]` constraints). Use WSL2 or Docker if you need encrypted-room support on Windows.

### Docker

A Docker image is available on GHCR with multi-platform support (amd64/arm64).

```bash
# Pull the image
docker pull ghcr.io/jeremiah-k/matrix-biblebot:latest

# Or build from source
git clone https://github.com/jeremiah-k/matrix-biblebot.git
cd matrix-biblebot
make use-source
make build
```

See [Running with Docker](#running-with-docker) for full setup instructions.

### From Source

```bash
git clone https://github.com/jeremiah-k/matrix-biblebot.git
cd matrix-biblebot
pip install '.[e2e]'  # Includes E2EE support
```

## Usage

### Supported Reference Formats

The bot understands various Bible reference formats:

| Format               | Example                 | Description                  |
| -------------------- | ----------------------- | ---------------------------- |
| **Single verse**     | `John 3:16`             | Gets one verse (KJV default) |
| **Verse range**      | `1 Cor 15:1-4`          | Gets multiple verses         |
| **Whole chapter**    | `Psalm 23`              | Gets entire chapter          |
| **With translation** | `John 3:16 esv`         | Specify ESV or KJV           |
| **Abbreviations**    | `jn 3:16`, `1co 15:1-4` | Short book names work        |

### Supported Translations

- **KJV (King James Version)** - Default, no setup required
- **ESV (English Standard Version)** - Requires free API key from [api.esv.org](https://api.esv.org/)

### Book Abbreviations

The bot recognizes many abbreviations: `gen` (Genesis), `exo` (Exodus), `matt` (Matthew), `jn` (John), `1co` (1 Corinthians), `rev` (Revelation), and many more. See [full list](docs/CONFIGURATION.md#book-abbreviations).

### Reference Detection

The bot responds only when a message is **entirely** a scripture reference.

| Should trigger   | Example           |
| ---------------- | ----------------- |
| Single verse     | `John 3:16`       |
| Verse range      | `1 Cor 15:1-4`    |
| Whole chapter    | `Psalm 23`        |
| With translation | `Romans 8:28 ESV` |

| Should NOT trigger | Example            |
| ------------------ | ------------------ |
| Prefix command     | `!bible John 3:16` |
| Mention            | `@bot Psalm 23`    |
| Embedded in text   | `I like John 3:16` |

### Bot Response

When you send a Bible reference, the bot will:

1. Add a ✅ reaction to your message
2. Reply with the verse text formatted like: `"Verse text - Reference 🕊️✝️"`

## Configuration

### Basic Setup

1. **Authenticate with Matrix**

   ```bash
   biblebot auth login
   ```

2. **Generate configuration file**

   ```bash
   biblebot config generate
   ```

3. **Edit the config file** at `~/.config/matrix-biblebot/config.yaml`
   (or `$BIBLEBOT_HOME/config.yaml` if `BIBLEBOT_HOME` is set):

   ```yaml
   matrix:
     room_ids:
       - "!your_room_id:your_homeserver_domain"
       - "#room_alias:your_homeserver_domain" # Aliases work too
   ```

4. **Run the bot**
   ```bash
   biblebot
   ```

### Advanced Configuration

For detailed configuration options including:

- End-to-end encryption setup
- Message splitting configuration
- API key configuration for ESV
- Poetry formatting options
- Custom file locations

See the [Configuration Guide](docs/CONFIGURATION.md).

## Running as a Service

For production use on Linux, install as a systemd user service:

```bash
biblebot service install
```

This creates a user service that starts automatically. Manage it with:

```bash
systemctl --user start biblebot.service     # Start
systemctl --user stop biblebot.service      # Stop
systemctl --user status biblebot.service    # Check status
```

### Running with Docker

Docker runtime uses `BIBLEBOT_HOME=/data` in the container, so runtime files live at:

- `/data/config.yaml`
- `/data/credentials.json`
- `/data/e2ee-store`

Use `BIBLEBOT_HOST_HOME` on the host side to choose where `/data` is mounted.

#### Prebuilt image flow (default)

```bash
# Initialize runtime directory + prebuilt compose mode
make setup

# Edit the config to add your room IDs
make edit

# Validate the config
make config-check

# Authenticate with Matrix (one-time)
make auth-login

# Optional: check saved authentication state
make auth-status

# Start the bot
make run
```

Docker images install the E2EE dependencies by default, so they are the recommended path for users who need E2EE on platforms where native dependency installation is difficult.

#### Build from source instead of prebuilt image

```bash
# Initialize runtime directory and default compose files
make setup

# Enable docker-compose.source.yaml override
make use-source

# Build the local image
make build

# Edit and validate config
make edit
make config-check

# Authenticate with Matrix (one-time)
make auth-login

# Start the bot
make run
```

Common Docker targets:

```bash
make pull
make build
make build-nocache
make config-check
make auth-login
make auth-status
make logs
make shell
make stop
make clean
make use-prebuilt
make use-source
```

If you run `docker compose` directly (without `make`), provide `UID` and `GID` so mounted files are owned by your host user.

```bash
env UID="$(id -u)" GID="$(id -g)" docker compose up -d
```

For repeated use, create a local `.env` file once. Direct `docker compose` users should set `BIBLEBOT_HOST_HOME` explicitly so config, credentials, and the E2EE store always use the same host runtime directory.

Ensure the host directory exists and is writable by the UID/GID used for the container:

```bash
mkdir -p ~/.config/matrix-biblebot
```

Then create the `.env` file and start the container:

```bash
printf 'UID=%s\nGID=%s\nBIBLEBOT_HOST_HOME=%s\n' \
  "$(id -u)" "$(id -g)" "$HOME/.config/matrix-biblebot" > .env
docker compose up -d
```

Useful direct compose operations:

```bash
docker compose run --rm biblebot biblebot config generate
docker compose run --rm biblebot biblebot config check
docker compose run --rm biblebot biblebot auth login
docker compose run --rm biblebot biblebot auth status
docker compose up -d
```

The sample compose file requires `BIBLEBOT_HOST_HOME` to be set to an absolute host path and mounts it to `/data` in the container. This ensures config, credentials, and the E2EE store persist across restarts without relying on Compose-specific nested environment expansion. Prebuilt images are published at `ghcr.io/jeremiah-k/matrix-biblebot`.

## CLI Commands

```bash
# Configuration
biblebot config generate    # Create sample config
biblebot config check       # Validate config

# Authentication
biblebot auth login         # Login to Matrix
biblebot auth logout        # Clear credentials
biblebot auth status        # Show auth status

# Service management
biblebot service install    # Install systemd service

# Running
biblebot                    # Start the bot
biblebot --log-level debug  # Debug mode
```

## Troubleshooting

**Common issues:**

- **"No credentials found"** → Run `biblebot auth login` first
- **Bot doesn't respond** → Check room IDs in config, ensure bot is invited
- **E2EE issues** → Install with `[e2e]` extra on Linux/macOS, verify device in Matrix client

For detailed troubleshooting, see [Troubleshooting Guide](docs/TROUBLESHOOTING.md).

## Documentation

- [Configuration Guide](docs/CONFIGURATION.md) - Detailed setup, options, and E2EE setup
- [Development Guide](docs/DEVELOPMENT.md) - Contributing and development setup
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Contributing

Contributions welcome! Please see [Development Guide](docs/DEVELOPMENT.md) for setup instructions and guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.
