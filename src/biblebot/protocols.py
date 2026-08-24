"""Structural type contracts used by the bot.

These protocols describe the surface area of dependencies the bot
needs from its Matrix client. They let us type ``BibleBot.client`` more
precisely without coupling the bot to ``nio.AsyncClient``, and they
let tests pass ``MagicMock`` instances safely while still catching
method-name typos through the type checker.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BotClient(Protocol):
    """Minimum Matrix client surface used by ``BibleBot``.

    Covers every method and attribute the bot calls on its injected
    Matrix client. Implementations include ``nio.AsyncClient`` in
    production and ``MagicMock`` instances in tests.
    """

    user_id: str | None
    device_id: str | None
    rooms: dict[str, Any]

    async def room_resolve_alias(self, room_alias: str) -> Any: ...

    async def join(self, room_id: str) -> Any: ...

    async def sync(
        self,
        *,
        timeout: int | None = ...,
        full_state: bool | None = ...,
        sync_filter: Any = ...,
        since: str | None = ...,
        set_presence: str | None = ...,
    ) -> Any: ...

    async def sync_forever(
        self,
        *,
        timeout: int | None = ...,
        full_state: bool | None = ...,
        sync_filter: Any = ...,
        since: str | None = ...,
        loop_sleep_time: int | None = ...,
        first_sync_filter: Any = ...,
        set_presence: str | None = ...,
    ) -> None: ...

    async def request_room_key(self, event: Any, tx_id: str | None = ...) -> Any: ...

    async def to_device(self, request: Any, tx_id: str | None = ...) -> Any: ...

    async def room_send(
        self,
        room_id: str,
        message_type: str,
        content: dict[str, Any],
        tx_id: str | None = ...,
        ignore_unverified_devices: bool = ...,
    ) -> Any: ...

    async def close(self) -> None: ...
