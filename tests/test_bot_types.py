"""Tests pinning the type contract for bot.py construction and helpers."""

from __future__ import annotations

import inspect
from typing import Mapping, get_type_hints

from biblebot.bot import (
    BibleBot,
    load_environment,
    make_api_request,
)


def test_load_environment_has_annotations():
    """Every parameter and the return must be annotated so call sites are checked."""
    sig = inspect.signature(load_environment)
    hints = get_type_hints(load_environment)
    for name in sig.parameters:
        assert name in hints, (
            f"load_environment parameter {name!r} must have a type annotation"
        )
    assert "return" in hints, "load_environment must declare a return annotation"


def test_make_api_request_has_annotations():
    sig = inspect.signature(make_api_request)
    hints = get_type_hints(make_api_request)
    for name in sig.parameters:
        assert name in hints, (
            f"make_api_request parameter {name!r} must have a type annotation"
        )
    assert "return" in hints, "make_api_request must declare a return annotation"


def test_biblebot_init_has_annotations():
    sig = inspect.signature(BibleBot.__init__)
    hints = get_type_hints(BibleBot.__init__)
    for name in list(sig.parameters)[1:]:
        assert name in hints, (
            f"BibleBot.__init__ parameter {name!r} must have a type annotation"
        )


def test_load_environment_tolerates_empty_config():
    """An empty config should be accepted; only env vars and warnings emitted."""
    from unittest.mock import patch
    import os

    with patch.dict(os.environ, {}, clear=True):
        token, keys = load_environment({}, "/nonexistent.yaml")
    assert token is None
    assert keys == {} or keys is None or isinstance(keys, Mapping)


def test_load_environment_returns_mapping_for_api_keys():
    """The api_keys return value must be a mapping, not None when defaults are used."""
    from unittest.mock import patch
    import os

    with patch.dict(os.environ, {}, clear=True):
        token, keys = load_environment({}, "/nonexistent.yaml")
    assert isinstance(keys, Mapping), (
        f"api_keys must always be a Mapping; got {type(keys).__name__}"
    )


def test_load_environment_reads_esv_env_var():
    from unittest.mock import patch
    import os

    with patch.dict(os.environ, {"ESV_API_KEY": "sentinel-12345"}, clear=False):
        _token, keys = load_environment({}, "/nonexistent.yaml")
    assert keys.get("esv") == "sentinel-12345"


def test_make_api_request_tolerates_missing_headers_and_params():
    """A missing headers dict and missing params must not raise TypeError."""
    import inspect

    sig = inspect.signature(make_api_request)
    assert sig.parameters["headers"].default is None
    assert sig.parameters["params"].default is None
    assert sig.parameters["session"].default is None
