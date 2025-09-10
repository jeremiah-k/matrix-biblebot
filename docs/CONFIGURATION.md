# Configuration Guide

This guide covers all configuration options for Matrix BibleBot.

## Quick Setup

1. **Authenticate with Matrix**

   ```bash
   biblebot auth login
   ```

2. **Generate configuration**

   ```bash
   biblebot config generate
   ```

3. **Edit configuration file** at `~/.config/matrix-biblebot/config.yaml`

4. **Validate configuration**
   ```bash
   biblebot config check
   ```

## Configuration File Structure

The configuration file uses YAML format with the following structure:

```yaml
version: 1

matrix:
  room_ids:
    - "!room1:example.com"
    - "#room-alias:example.com"
  e2ee:
    enabled: false
    store_path: null

bot:
  default_translation: kjv
  cache_enabled: true
  max_message_length: 2000
  preserve_poetry_formatting: false
  split_message_length: 0
  detect_references_anywhere: false

api_keys:
  esv: null
```

## Matrix Configuration

### Room IDs

Configure which Matrix rooms the bot should respond in:

```yaml
matrix:
  room_ids:
    - "!AbCdEfGhIjKlMnOpQr:matrix.example.com" # Room ID
    - "#bible-study:matrix.example.com" # Room alias
```

**Room IDs vs Aliases:**

- **Room IDs** (starting with `!`) are permanent identifiers
- **Room aliases** (starting with `#`) are human-readable names that resolve to room IDs
- The bot automatically resolves aliases to room IDs at startup
- Use either format in your configuration

**Finding Room IDs:**

- In Element: Room Settings → Advanced → Internal room ID
- In other clients: Check room details or developer tools

### End-to-End Encryption (E2EE)

Enable E2EE support for encrypted rooms:

```yaml
matrix:
  e2ee:
    enabled: true
    store_path: null # Optional: custom path for E2EE store
```

**Requirements:**

- Install with E2EE support: `pipx install 'matrix-biblebot[e2e]'`
- Use `biblebot auth login` (access tokens don't support E2EE)

**E2EE Store:**

- Default location: `~/.config/matrix-biblebot/e2ee-store`
- Contains cryptographic keys - keep secure
- If lost, bot can't decrypt old messages

## Bot Behavior Configuration

### Default Translation

Set the default Bible translation:

```yaml
bot:
  default_translation: kjv # Options: kjv, esv
```

### Message Length and Splitting

Control how long messages are handled:

```yaml
bot:
  max_message_length: 2000 # Maximum single message length
  split_message_length: 1000 # Split messages longer than this (0 = disabled)
```

**Message Splitting Features:**

- Splits at word boundaries, not mid-word
- Reference and suffix only appear on final message
- Automatic fallback if splitting isn't practical
- Built-in rate limiting for multiple messages

**Example:** Psalm 119 would be split into multiple messages, with only the last showing "Psalm 119:1-176 🕊️✝️"

### Poetry Formatting

Preserve line breaks in poetic texts:

```yaml
bot:
  preserve_poetry_formatting: true
```

When enabled:

- Preserves line breaks in Psalms, Proverbs, etc.
- Cleans up excess whitespace
- Converts to HTML `<br />` tags in formatted messages

### Reference Detection

Control how the bot detects Bible references:

```yaml
bot:
  detect_references_anywhere: false

**Note:** Setting this to `true` may cause unintended triggers in bridged or high-traffic rooms.
```

- `false` (default): Only detects references that are the entire message
- `true`: Detects references anywhere in messages (useful with Matrix bridges)

### Caching

Enable verse caching for better performance:

```yaml
bot:
  cache_enabled: true # Default: true
```

## API Keys

### ESV API Key

To use the English Standard Version translation:

1. **Get a free API key** from [api.esv.org](https://api.esv.org/)
2. **Add to configuration:**
   ```yaml
   api_keys:
     esv: "your-api-key-here"
   ```

**Alternative:** Set as environment variable:

```bash
export ESV_API_KEY="your-api-key-here"
```

Environment variables take precedence over config file values.

## File Locations

### Default Paths

- **Configuration:** `~/.config/matrix-biblebot/config.yaml`
- **Credentials:** `~/.config/matrix-biblebot/credentials.json`
- **E2EE Store:** `~/.config/matrix-biblebot/e2ee-store/`

### Custom Configuration Path

Specify a different config location:

```bash
biblebot --config /path/to/your/config.yaml
```

### Directory Permissions

The bot automatically sets secure permissions:

- Config directory: `0700` (owner read/write/execute only)
- Credentials file: `0600` (owner read/write only)

## Book Abbreviations

The bot recognizes many book abbreviations:

### Old Testament

- **Genesis:** `gen`, `ge`, `gn`
- **Exodus:** `exo`, `ex`
- **Leviticus:** `lev`, `le`, `lv`
- **Numbers:** `num`, `nu`, `nm`
- **Deuteronomy:** `deut`, `de`, `dt`
- **Joshua:** `josh`, `jos`
- **Judges:** `judg`, `jdg`, `jg`
- **Ruth:** `ruth`, `ru`
- **1 Samuel:** `1 sam`, `1sa`, `1s`
- **2 Samuel:** `2 sam`, `2sa`, `2s`
- **1 Kings:** `1 kings`, `1ki`, `1k`
- **2 Kings:** `2 kings`, `2ki`, `2k`
- **1 Chronicles:** `1 chron`, `1ch`
- **2 Chronicles:** `2 chron`, `2ch`
- **Ezra:** `ezra`, `ezr`
- **Nehemiah:** `neh`, `ne`
- **Esther:** `est`, `es`
- **Job:** `job`, `jb`
- **Psalms:** `psalm`, `psalms`, `psa`, `ps`
- **Proverbs:** `prov`, `pro`, `pr`
- **Ecclesiastes:** `eccles`, `ecc`, `ec`
- **Song of Solomon:** `song`, `sos`, `so`, `song of songs`, `cant`, `canticles`
- **Isaiah:** `isa`, `is`
- **Jeremiah:** `jer`, `je`
- **Lamentations:** `lam`, `la`
- **Ezekiel:** `ezek`, `eze`, `ez`
- **Daniel:** `dan`, `da`, `dn`
- **Hosea:** `hos`, `ho`
- **Joel:** `joel`, `joe`, `jl`
- **Amos:** `amos`, `am`
- **Obadiah:** `obad`, `ob`
- **Jonah:** `jonah`, `jon`
- **Micah:** `mic`, `mi`
- **Nahum:** `nah`, `na`
- **Habakkuk:** `hab`, `ha`
- **Zephaniah:** `zeph`, `zep`, `zp`
- **Haggai:** `hag`, `hg`
- **Zechariah:** `zech`, `zec`, `zc`
- **Malachi:** `mal`, `ml`

### New Testament

- **Matthew:** `matt`, `mt`
- **Mark:** `mark`, `mar`, `mk`
- **Luke:** `luke`, `lk`
- **John:** `john`, `jn`
- **Acts:** `acts`, `ac`
- **Romans:** `rom`, `ro`
- **1 Corinthians:** `1 cor`, `1co`
- **2 Corinthians:** `2 cor`, `2co`
- **Galatians:** `gal`, `ga`
- **Ephesians:** `eph`, `ep`
- **Philippians:** `phil`, `phi`, `php`
- **Colossians:** `col`, `co`
- **1 Thessalonians:** `1 thess`, `1th`
- **2 Thessalonians:** `2 thess`, `2th`
- **1 Timothy:** `1 tim`, `1ti`
- **2 Timothy:** `2 tim`, `2ti`
- **Titus:** `titus`, `ti`
- **Philemon:** `philem`, `phm`, `pm`
- **Hebrews:** `heb`, `he`
- **James:** `james`, `jm`
- **1 Peter:** `1 pet`, `1pe`, `1pt`
- **2 Peter:** `2 pet`, `2pe`, `2pt`
- **1 John:** `1 john`, `1jn`
- **2 John:** `2 john`, `2jn`
- **3 John:** `3 john`, `3jn`
- **Jude:** `jude`, `jd`
- **Revelation:** `rev`, `re`

## Environment Variables

Environment variables override config file values:

- `ESV_API_KEY` - ESV API key
- `MATRIX_ACCESS_TOKEN` - Legacy access token (deprecated)
- `MATRIX_HOMESERVER` - Legacy homeserver URL (deprecated)
- `MATRIX_USER_ID` - Legacy user ID (deprecated)

**Note:** Legacy environment variables are deprecated. Use `biblebot auth login` instead.

## Validation

Check your configuration:

```bash
biblebot config check
```

This validates:

- YAML syntax
- Required fields
- Room ID formats
- API key presence
- E2EE configuration

## Migration from Legacy Setup

If you have existing environment variables:

1. **Remove legacy variables:**

   ```bash
   unset MATRIX_ACCESS_TOKEN MATRIX_HOMESERVER MATRIX_USER_ID
   ```

2. **Use modern authentication:**

   ```bash
   biblebot auth login
   ```

3. **Update configuration file** to remove any hardcoded homeserver/user settings

The new authentication method provides better security and E2EE support.
