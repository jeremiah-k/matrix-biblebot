# Testing

Prepare the development environment as described in [Development](../DEVELOPMENT.md):

```bash
uv sync --locked --extra test --extra e2e
uv run --locked --no-sync pytest
```

Coverage is on by default. Use `--no-cov` for focused iterations. Warnings are
errors; close resources and await coroutines instead of suppressing warnings.

## What the suite proves

Tests exercise configuration, CLI exit statuses, triggers, lookup contracts,
formatting, cache behavior, send retries, authentication, and runtime paths.
The CLI contract tests run a separate Python process so they also exercise
real imports and argument parsing.

`conftest.py` replaces the Matrix client and crypto modules with test doubles
before application imports. It retains real `nio.responses` classes for send
response inspection. These tests do not connect to a homeserver and cannot
prove encrypted-room interoperability. Some historical pattern suites use
synthetic scenarios; prefer regressions against application functions when
adding coverage.

Package and Docker CI smoke checks run outside these mocks. They establish
that distributions contain the entry point and packaged assets, and that the
container can import its crypto provider. A real Matrix round trip needs a
dedicated bot account and encrypted test room.

## Matrix client doubles

Use a regular mock for synchronous methods and an async mock for coroutines:

```python
from unittest.mock import AsyncMock, MagicMock
from biblebot.protocols import BotClient

client = MagicMock(spec=BotClient)
client.user_id = "@bot:example.org"
client.device_id = "DEVICE"
client.rooms = {}
client.room_send = AsyncMock(return_value=None)
client.room_resolve_alias = AsyncMock()
client.join = AsyncMock()
client.sync = AsyncMock()
client.sync_forever = AsyncMock()
client.close = AsyncMock()
```

`restore_login` and `add_event_callback` are synchronous startup methods.
`room_resolve_alias`, `room_send`, `join`, `login`, `logout`, `sync`,
`sync_forever`, `keys_upload`, `to_device`, and `request_room_key` are async.

nio returns `ErrorResponse` objects for Matrix errors. It raises exceptions
for transport/protocol failures. Use real response classes to test this
contract:

```python
from nio.responses import RoomSendError

client.room_send = AsyncMock(
    return_value=RoomSendError("rate limited", "M_LIMIT_EXCEEDED", retry_after_ms=1000)
)
```

Do not raise response dataclasses such as `RoomResolveAliasError` as
exceptions. Test error returns and actual transport exceptions separately.

## CLI tests

Patch the coroutine that the command invokes. A replacement for `run_async`
must consume its coroutine; returning without awaiting it creates warnings.
For parser and process-status contracts, use a subprocess as in
`tests/test_cli_contract.py`.

```python
import sys
from biblebot import cli

async def no_op(*args, **kwargs):
    return None

def test_cli_startup(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("matrix_room_ids: ['!room:example.org']")
    monkeypatch.setattr(cli, "bot_main", no_op)
    monkeypatch.setattr(sys, "argv", ["biblebot", "--config", str(config)])
    cli.main()
```

## Passage tests

Patch the lookup module's HTTP seam when checking response validation:

```python
from unittest.mock import AsyncMock
from biblebot import passages

async def test_kjv_lookup(monkeypatch):
    monkeypatch.setattr(
        passages, "make_api_request",
        AsyncMock(return_value={"text": " Verse text ", "reference": "John 3:16"}),
    )
    assert await passages.get_kjv_text("John 3:16") == ("Verse text", "John 3:16")
```

When testing the bot's orchestration, patch `biblebot.bot.get_bible_text`.
When testing HTTP behavior, supply an aiohttp-style async context manager or
use the pytest-aiohttp fixture. The implementation uses aiohttp, not requests.

## Isolation and cleanup

Use temporary runtime homes and monkeypatch environment settings. Avoid
writing to a real credentials file or crypto store. Copy nested config
fixtures before mutating them. The shared cache is cleared between tests.

Lifecycle fixtures stub the startup release check automatically. Update-check
tests use the real update orchestration with explicit HTTP doubles. Keep
external services behind those doubles so unit tests are independent of GitHub
availability and network transport teardown timing.

`pytest-asyncio` owns each test's event loop. A test that calls `BibleBot.start`
must close the bot's HTTP session in a `finally` block. Set `sync_forever` to a
finite async double so a startup test can finish.

## Trigger tests

Use the actual detection interface:

```python
from biblebot.triggers import detect_trigger

def test_whole_message_policy():
    assert detect_trigger("John 3:16", "kjv").passage == "John 3:16"
    assert detect_trigger("I like John 3:16", "kjv") is None
```

Add regressions for the behavior a caller observes, including failures and
cancellation. Assertions about implementation source text or synthetic
examples are not substitutes for executing the application contract.
