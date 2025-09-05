# Matrix BibleBot

A simple Matrix bot that fetches Bible verses using APIs from [bible-api.com](https://bible-api.com) & [esv.org](https://api.esv.org/)

## Features

- **Bible Verse Fetching**: Support for KJV and ESV translations with easy extensibility
- **Message Splitting**: Configurable splitting of long passages into multiple messages
- **End-to-End Encryption**: Optional E2EE support for encrypted Matrix rooms
- **Smart Configuration**: Interactive setup with room alias support and validation
- **Production Ready**: Rate limiting, error handling, and systemd service integration

## Supported Translations

- **King James Version (KJV)** - Default, no API key required
- **English Standard Version (ESV)** - Requires free API key from [api.esv.org](https://api.esv.org/)
- **Easily extensible** - Architecture supports adding additional translations

## Installation

### Option 1: Install with [pipx](https://pypa.github.io/pipx/) (Recommended)

```bash
pipx install matrix-biblebot
```

To enable Matrix end-to-end encryption (E2EE):

```bash
pipx install 'matrix-biblebot[e2e]'
```

### Option 2: Install with pip

```bash
pip install matrix-biblebot
# or with E2EE support
pip install 'matrix-biblebot[e2e]'
```

### Option 3: Install from Source

```bash
git clone https://github.com/jeremiah-k/matrix-biblebot.git
cd matrix-biblebot
pip install .  # For normal use
# OR
pip install -e .  # For development
```

## Configuration

### Generate Configuration Files

The easiest way to get started is to generate the configuration files:

```bash
biblebot --generate-config
```

This will create a sample config file (`config.yaml`) in the `~/.config/matrix-biblebot/` directory.
If a config file is missing when you run `biblebot`, the CLI will offer to generate this starter file for you.

You can also specify a custom location:

```bash
biblebot --generate-config --config /path/to/your/config.yaml
```

### Authentication

The bot uses secure session-based authentication that supports E2EE:

```bash
biblebot auth login
```

This will:

1. Prompt for your Matrix homeserver, username, and password
2. Log in and save credentials locally (`credentials.json`) with owner-only permissions (0600)
3. Enable E2EE support if dependencies are installed

**Benefits of proper authentication:**

- ✅ Supports End-to-End Encryption (E2EE)
- ✅ Secure credential storage
- ✅ Automatic session management
- ✅ Device verification support

To delete credentials and the E2EE store:

```bash
biblebot auth logout
```

**Legacy Token Setup (Deprecated):**
⚠️ Manual access tokens are deprecated and do NOT support E2EE. If you have existing `MATRIX_ACCESS_TOKEN` environment variables, consider migrating to `biblebot auth login` for E2EE support.

### Edit Configuration Files

1. **Edit the config.yaml file** with your Matrix room information:

```yaml
# Matrix server and user details are handled by 'biblebot auth login'
matrix:
  room_ids:
    - "!your_room_id:your_homeserver_domain"
    - "#room_alias:your_homeserver_domain" # Room aliases are supported
```

2. **Optionally set API keys** in `config.yaml` (preferred). They can also be set as environment variables, which will take precedence over `config.yaml`.

The bot will automatically resolve room aliases to room IDs at startup. You can use either room IDs (starting with !) or room aliases (starting with #) in your configuration.

### Message Splitting Configuration

For long Bible passages, you can enable message splitting to break them into multiple messages:

```yaml
bot:
  # Split messages longer than this into multiple parts (disabled by default)
  split_message_length: 1000 # Characters per message chunk
  max_message_length: 2000 # Maximum total message length
```

**Message Splitting Features:**

- **Smart Word Boundaries**: Messages are split at word boundaries, not mid-word
- **Reference Preservation**: Bible reference and bot suffix only appear on the final message
- **Automatic Fallback**: Falls back to single-message mode when splitting isn't practical
- **Rate Limiting**: Built-in rate limiting handles multiple message sending gracefully

**Example**: A long passage like Psalm 119 would be split into multiple messages, with only the last message showing "Psalm 119:1-176 🕊️✝️"

### Configuration File Locations

By default, the bot looks for:

- Configuration file: `~/.config/matrix-biblebot/config.yaml`
- Credentials file: `~/.config/matrix-biblebot/credentials.json` (created by `biblebot auth login`)

You can specify a different config location when running the bot:

```bash
biblebot --config /path/to/your/config.yaml
```

### End-to-End Encryption (E2EE) Configuration

The bot supports End-to-End Encryption for secure communication in encrypted rooms. To enable E2EE:

1. **Install E2EE dependencies** (if not already installed):

   ```bash
   pip install 'matrix-biblebot[e2e]'
   ```

2. **Enable E2EE in your config.yaml**:

   ```yaml
   # E2EE Configuration
   e2ee:
     enabled: true # Enable E2EE support
     store_path: null # Optional: custom path for E2EE store
     trust_on_first_use: true # Trust new devices automatically
   ```

3. **First-time E2EE setup**:
   - The bot will create an E2EE store at `~/.config/matrix-biblebot/e2ee-store`
   - On first run, the bot will generate and upload encryption keys
   - You may need to verify the bot's device in your Matrix client

**E2EE Notes:**

- E2EE dependencies are automatically installed with `matrix-biblebot[e2e]`
- The bot can work in both encrypted and unencrypted rooms simultaneously
- E2EE store contains sensitive cryptographic keys - keep it secure
- If you lose the E2EE store, the bot won't be able to decrypt old messages

## Usage

### Quick Start

1. Install the bot: `pipx install matrix-biblebot`
2. Run the bot: `biblebot` (it will guide you through setup)
3. Follow the interactive prompts to:
   - Generate configuration file
   - Edit your Matrix room IDs (server/user are handled by 'biblebot auth login')
   - Authenticate with your Matrix account
4. The bot will start automatically once configured

### Running the Bot

After configuring the bot, you can run it in several ways:

```bash
# Run with default configuration
biblebot

# Run with custom config location
biblebot --config /path/to/config.yaml

# Run with debug logging
biblebot --log-level debug

### Encrypted Rooms (Optional)

To use encrypted Matrix rooms, install with the `e2e` extra and enable E2EE in config. See docs/E2EE.md for a full guide.
```

### Running as a Service (Recommended)

For a persistent installation, set up BibleBot as a systemd user service:

```bash
biblebot --install-service
```

This will:

1. Create a systemd user service file
2. Guide you through enabling the service to start at boot
3. Offer to start the service immediately

Once installed, manage the service with standard systemd commands:

```bash
systemctl --user start biblebot.service    # Start the service
systemctl --user stop biblebot.service     # Stop the service
systemctl --user restart biblebot.service  # Restart the service
systemctl --user status biblebot.service   # Check service status
```

### Command-line Options

```text
usage: biblebot [-h] [--config CONFIG] [--log-level {error,warning,info,debug}] [--generate-config] [--install-service] [--version]

options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to config file (default: ~/.config/matrix-biblebot/config.yaml)
  --log-level {error,warning,info,debug}
                        Set logging level (default: info)
  --generate-config     Generate sample config files at the specified path
  --install-service     Install or update the systemd user service
  --version             show program's version number and exit
```

### Interacting with the Bot

1. **Invite the bot** to the rooms listed in your `config.yaml` file
2. **Send Bible verse references** in any of these formats. The bot understands many common book abbreviations (e.g., `jn` for John, `1co` for 1 Corinthians).

| Format           | Example         | Description                        |
| ---------------- | --------------- | ---------------------------------- |
| Simple reference | `John 3:16`     | Single verse (uses KJV by default) |
| Range reference  | `1 Cor 15:1-4`  | Multiple verses                    |
| With translation | `John 3:16 esv` | Specify translation (KJV or ESV)   |
| Abbreviated      | `jn 3:16`       | Book names can be abbreviated      |

The bot will respond with the requested scripture passage and add a ✅ reaction to your message.

## Development

Contributions are welcome! Feel free to open issues or submit pull requests.
