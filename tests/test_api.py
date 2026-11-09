"""Unit tests for the pure ``_items`` helper. Plain pytest, no HA/aiohttp.

``api.py`` imports ``aiohttp`` at module scope and would, via the package
``__init__``, drag in Home Assistant, neither of which is installed under plain
``pytest``. We stub just enough of those two names to import the real ``_items``
function rather than re-implementing it, so the test exercises production code.
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "filc"

# Stub aiohttp: only ``ClientTimeout(total=...)`` is evaluated at import time.
_aiohttp = types.ModuleType("aiohttp")


class _ClientTimeout:
    def __init__(self, **kwargs: object) -> None:
        pass


_aiohttp.ClientTimeout = _ClientTimeout


class _ClientError(Exception):
    pass


_aiohttp.ClientError = _ClientError
sys.modules["aiohttp"] = _aiohttp

# Register a stub package so ``from .const import API_PREFIX`` resolves without
# executing ``custom_components/filc/__init__.py`` (which imports Home Assistant).
_pkg = types.ModuleType("custom_components.filc")
_pkg.__path__ = [str(COMPONENT_DIR)]
sys.modules["custom_components.filc"] = _pkg

from custom_components.filc.api import (  # noqa: E402
    FilcApi,
    FilcApiError,
    _items,
    parse_door_target,
)


def test_items_dict_with_items():
    assert _items({"items": [{"id": "a"}, {"id": "b"}], "total": 2}) == [
        {"id": "a"},
        {"id": "b"},
    ]


def test_items_dict_without_items():
    assert _items({"total": 5}) == []
    assert _items({}) == []
    assert _items({"items": None}) == []


def test_items_bare_list():
    assert _items([1, 2, 3]) == [1, 2, 3]
    assert _items([]) == []


def test_items_none():
    assert _items(None) == []


def test_items_non_list_garbage():
    assert _items("nope") == []
    assert _items(42) == []
    assert _items(3.14) == []


# --- Fake async session: every request is recorded, nothing leaves the process ---


class _FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._payload = payload

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeRequest:
    def __init__(self, session: "FakeSession", method: str, url: str, **kwargs) -> None:
        self._session = session
        self._method = method
        self._url = url
        self._kwargs = kwargs

    async def __aenter__(self) -> _FakeResponse:
        self._session.calls.append(
            {
                "method": self._method,
                "url": self._url,
                "headers": self._kwargs.get("headers"),
                "json": self._kwargs.get("json"),
                "params": self._kwargs.get("params"),
            }
        )
        return _FakeResponse(self._session.status, self._session.payload)

    async def __aexit__(self, *exc_info) -> bool:
        return False


class FakeSession:
    def __init__(self, status: int = 200, payload: object = None) -> None:
        self.status = status
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs) -> _FakeRequest:
        return _FakeRequest(self, "GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> _FakeRequest:
        return _FakeRequest(self, "POST", url, **kwargs)


def _api(status: int = 200, payload: object = None, key: str = "secret"):
    session = FakeSession(status, payload)
    return FilcApi(session, "https://filc.example", key), session


def test_cards_gets_self_cards_and_unwraps_items():
    api, session = _api(payload={"items": [{"id": "card-1"}], "total": 1})

    assert asyncio.run(api.cards()) == [{"id": "card-1"}]

    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://filc.example/api/doorlock/self/cards"
    assert call["headers"]["Authorization"] == "Bearer secret"


def test_activate_card_posts_device_id():
    api, session = _api(payload={"ok": True})

    asyncio.run(api.activate_card("card-1", "dev-1"))

    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == (
        "https://filc.example/api/doorlock/self/cards/card-1/activate"
    )
    assert call["json"] == {"deviceId": "dev-1"}


def test_activate_card_without_device_posts_empty_object():
    api, session = _api(payload={"ok": True})

    asyncio.run(api.activate_card("card-1"))

    assert session.calls[0]["json"] == {}


def test_activate_card_conflict_raises_with_status_and_detail():
    api, _session = _api(status=409, payload={"code": "CONFLICT", "message": "frozen"})

    with pytest.raises(FilcApiError) as excinfo:
        asyncio.run(api.activate_card("card-1", "dev-1"))

    assert excinfo.value.status == 409
    assert "CONFLICT: frozen" in str(excinfo.value)


def test_parse_door_target():
    assert parse_door_target("card-1|dev-1") == ("card-1", "dev-1")
    assert parse_door_target("card-1") == ("card-1", "")
    assert parse_door_target("") == ("", "")
