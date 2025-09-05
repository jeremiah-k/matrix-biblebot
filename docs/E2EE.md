# Matrix End-to-End Encryption (E2EE)

BibleBot supports optional Matrix End-to-End Encryption so it can participate in encrypted rooms. E2EE is disabled by default and can be enabled with an extra dependency and configuration change.

**Important**: E2EE requires proper authentication using `biblebot auth login`. Manual access tokens (MATRIX_ACCESS_TOKEN) do NOT support E2EE.

## Install with E2EE

Recommended (pipx):

```bash
pipx install 'matrix-biblebot[e2e]'
```

Or pip:

```bash
pip install 'matrix-biblebot[e2e]'
```

This installs all cryptographic dependencies needed for E2EE support, including pre-compiled libraries. No additional system packages are required.

**Requirements:**

- Python 3.9+
- Linux/macOS (Windows not supported for E2EE due to `python-olm` dependency)

## Enable in Config

Add an `e2ee` section under `matrix` in your config (usually `~/.config/matrix-biblebot/config.yaml`):

The bot will use the homeserver and user from your 'biblebot auth login' session.
You only need to configure the room IDs and E2EE settings:

```yaml
matrix:
  room_ids:
    - "!roomid:your-matrix-server.org"
  e2ee:
    enabled: true
    # Optional custom store path (default: ~/.config/matrix-biblebot/e2ee-store)
    # store_path: /path/to/e2ee-store
```

## Authenticate

Use the built-in auth flow (recommended):

```bash
biblebot auth login
```

This saves credentials to `~/.config/matrix-biblebot/credentials.json` and prepares an encryption store. If you run the command again, it will detect the existing session and ask for confirmation before creating a new one.

To remove credentials and the local store:

```bash
biblebot auth logout
```

## Behavior

- When E2EE is enabled, BibleBot initializes a store, restores the session from `credentials.json`, and uploads keys if needed.
- Decryption failures automatically trigger key requests; messages typically decrypt on the next sync.
- Unencrypted rooms continue to work normally alongside encrypted rooms.

## Windows Limitation

E2EE is not available on Windows due to `python-olm` dependency constraints. Windows users can still:

- Use `biblebot auth login` for secure authentication
- Run the bot in unencrypted rooms
- Use all other bot features except E2EE

## Security Notes

- Protect `~/.config/matrix-biblebot/credentials.json` and the E2EE store directory.
- Device verification is not required for automated bots; BibleBot operates with sensible defaults.
