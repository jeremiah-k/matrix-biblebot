# Matrix End-to-End Encryption (E2EE)

BibleBot supports optional Matrix End-to-End Encryption so it can participate in encrypted rooms. E2EE is disabled by default and can be enabled with an extra dependency and a small config change.

## Install with E2EE

Recommended (pipx):

```bash
pipx install 'matrix-biblebot[e2e]'
```

Or pip:

```bash
pip install 'matrix-biblebot[e2e]'
```

Requirements:

- Python 3.9+
- Linux/macOS (Windows not supported for E2EE due to `python-olm`)

## Enable in Config

Add an `e2ee` section under `matrix` in your config (usually `~/.config/matrix-biblebot/config.yaml`):

```yaml
matrix_homeserver: https://your-matrix-server.org
matrix_user: "@your-bot:your-matrix-server.org"
matrix_room_ids:
  - "!roomid:your-matrix-server.org"

matrix:
  e2ee:
    enabled: true
    # Optional custom store path (default: ~/.config/matrix-biblebot/e2ee-store)
    # store_path: /path/to/e2ee-store
```

## Authenticate

Use the built-in auth flow (recommended):

```bash
biblebot --auth-login
```

This saves credentials to `~/.config/matrix-biblebot/credentials.json` and prepares an encryption store. If you run the command again, it will detect the existing session and ask for confirmation before creating a new one.

To remove credentials and the local store:

```bash
biblebot --auth-logout
```

## Behavior

- When E2EE is enabled, BibleBot initializes a store, restores the session from `credentials.json`, and uploads keys if needed.
- Decryption failures automatically trigger key requests; messages typically decrypt on the next sync.
- Unencrypted rooms continue to work normally alongside encrypted rooms.

## Windows Limitation

E2EE is not available on Windows due to `python-olm` constraints. You can still use `--auth-login` and run without E2EE.

## Security Notes

- Protect `~/.config/matrix-biblebot/credentials.json` and the E2EE store directory.
- Device verification is not required for automated bots; BibleBot operates with sensible defaults.
