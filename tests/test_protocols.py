"""Tests for structural type contracts used by the bot."""

from __future__ import annotations

import inspect

from biblebot.protocols import BotClient


class _FakeClient:
    """Stand-in implementing every method/attribute on BotClient."""

    user_id: str | None = "@bot:example.org"
    device_id: str | None = "DEVICE"
    rooms: dict[str, object] = {}

    async def room_resolve_alias(self, room_alias: str) -> object:
        return None

    async def join(self, room_id: str) -> object:
        return None

    async def sync(
        self,
        *,
        timeout: int | None = None,
        full_state: bool | None = None,
        sync_filter: object = None,
        since: str | None = None,
        set_presence: str | None = None,
    ) -> object:
        return None

    async def sync_forever(
        self,
        *,
        timeout: int | None = None,
        full_state: bool | None = None,
        sync_filter: object = None,
        since: str | None = None,
        loop_sleep_time: int | None = None,
        first_sync_filter: object = None,
        set_presence: str | None = None,
    ) -> None:
        return None

    async def request_room_key(self, event: object, tx_id: str | None = None) -> object:
        return None

    async def to_device(self, request: object, tx_id: str | None = None) -> object:
        return None

    async def room_send(
        self,
        room_id: str,
        message_type: str,
        content: dict[str, object],
        tx_id: str | None = None,
        ignore_unverified_devices: bool = False,
    ) -> object:
        return None

    async def close(self) -> None:
        return None


def test_bot_client_protocol_lists_required_attributes():
    """BotClient must declare every attribute the bot reads on the client."""
    annotations = getattr(BotClient, "__annotations__", {})
    assert "user_id" in annotations
    assert "device_id" in annotations
    assert "rooms" in annotations


def test_bot_client_protocol_lists_required_methods():
    """BotClient must declare every method the bot calls on the client."""
    methods = {name for name in dir(BotClient) if not name.startswith("_")}
    required = {
        "room_resolve_alias",
        "join",
        "sync",
        "sync_forever",
        "request_room_key",
        "to_device",
        "room_send",
        "close",
    }
    missing = required - methods
    assert not missing, f"BotClient is missing methods: {sorted(missing)}"


def test_fake_client_satisfies_bot_client_protocol():
    """A client that implements every method/attribute should be a BotClient."""
    assert isinstance(_FakeClient(), BotClient)


def test_async_methods_actually_coroutine():
    """All async methods on the protocol must be coroutine functions.

    Inspect the protocol declarations directly so changing the protocol from
    async to sync (or vice versa) is detected here, not just changing the test
    fake.
    """
    for name in (
        "room_resolve_alias",
        "join",
        "sync",
        "sync_forever",
        "request_room_key",
        "to_device",
        "room_send",
        "close",
    ):
        method = getattr(BotClient, name)
        assert inspect.iscoroutinefunction(
            method
        ), f"BotClient.{name} must be declared async, got {method!r}"


def test_bot_client_is_runtime_checkable():
    """BotClient should support isinstance() checks at runtime."""
    assert hasattr(BotClient, "_is_runtime_protocol")
    assert BotClient._is_runtime_protocol
