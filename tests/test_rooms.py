"""Tests for pure Matrix room identifier helpers."""

from biblebot.rooms import (
    is_alias,
    is_placeholder_room_id,
    merge_resolved_entries,
    read_room_ids,
)


def test_is_alias_only_matches_hash_prefix():
    assert is_alias("#bible-studies:example.org")
    assert not is_alias("!abc:example.org")
    assert not is_alias(None)
    assert not is_alias("")


def test_is_placeholder_room_id_matches_documented_placeholders():
    assert is_placeholder_room_id("#example:example.org")
    assert is_placeholder_room_id("!example:example.org")
    assert is_placeholder_room_id("!your_room_id:matrix.org")
    assert is_placeholder_room_id("#bible:your_homeserver_domain")
    assert not is_placeholder_room_id("!abc:matrix.org")
    assert not is_placeholder_room_id(None)


def test_read_room_ids_prefers_nested_schema():
    config = {
        "matrix": {"room_ids": ["#bible:example.org", "!abc:example.org"]},
        "matrix_room_ids": ["#legacy:example.org"],
    }

    assert read_room_ids(config) == ["#bible:example.org", "!abc:example.org"]


def test_read_room_ids_falls_back_to_legacy_schema():
    config = {"matrix_room_ids": ["#bible:example.org"]}

    assert read_room_ids(config) == ["#bible:example.org"]


def test_read_room_ids_tolerates_missing_or_malformed_values():
    assert read_room_ids({}) == []
    assert read_room_ids(None) == []
    assert read_room_ids({"matrix": {"room_ids": "not a list"}}) == []
    assert read_room_ids({"matrix_room_ids": ["ok", 5, None]}) == ["ok"]


def test_merge_resolved_entries_preserves_first_occurrence_order():
    merged = merge_resolved_entries(
        ["#bible:example.org", "!abc:example.org"],
        ["!xyz:example.org", "!abc:example.org"],
    )

    assert merged == ["#bible:example.org", "!abc:example.org", "!xyz:example.org"]


def test_merge_resolved_entries_drops_non_string_entries():
    merged = merge_resolved_entries(["!abc:example.org"], [None, 1, "!abc:example.org"])

    assert merged == ["!abc:example.org"]


async def test_alias_resolution_updates_join_list_and_message_admission():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from biblebot.bot import BibleBot

    client = MagicMock()
    client.rooms = {}
    client.room_resolve_alias = AsyncMock(
        return_value=SimpleNamespace(room_id="!resolved:server")
    )
    client.join = AsyncMock(return_value=SimpleNamespace(room_id="!resolved:server"))
    config = {
        "matrix": {"room_ids": ["#alias:server", "!resolved:server"]},
        "matrix_room_ids": ["#stale:server"],
    }
    bot = BibleBot(config, client)
    await bot.resolve_aliases()
    await bot.ensure_joined_rooms()
    assert config["matrix"]["room_ids"] == ["!resolved:server"]
    assert config["matrix_room_ids"] == ["!resolved:server"]
    assert bot._room_id_set == {"!resolved:server"}
    client.room_resolve_alias.assert_awaited_once_with("#alias:server")
    client.join.assert_awaited_once_with("!resolved:server")


async def test_failed_alias_resolution_retains_entry_for_retry():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from biblebot.bot import BibleBot

    client = MagicMock()
    client.room_resolve_alias = AsyncMock(
        return_value=SimpleNamespace(message="not found")
    )
    bot = BibleBot({"matrix": {"room_ids": ["#alias:server"]}}, client)
    await bot.resolve_aliases()
    assert bot.config["matrix_room_ids"] == ["#alias:server"]
    assert bot._room_id_set == set()
