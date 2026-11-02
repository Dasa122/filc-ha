"""Unit tests for the pure ``_items`` helper. Plain pytest, no HA/aiohttp.

``api.py`` imports ``aiohttp`` at module scope and would, via the package
``__init__``, drag in Home Assistant, neither of which is installed under plain
``pytest``. We stub just enough of those two names to import the real ``_items``
function rather than re-implementing it, so the test exercises production code.
"""

import sys
import types
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "filc"

# Stub aiohttp: only ``ClientTimeout(total=...)`` is evaluated at import time.
_aiohttp = types.ModuleType("aiohttp")


class _ClientTimeout:
    def __init__(self, **kwargs: object) -> None:
        pass


_aiohttp.ClientTimeout = _ClientTimeout
_aiohttp.ClientError = Exception
sys.modules["aiohttp"] = _aiohttp

# Register a stub package so ``from .const import API_PREFIX`` resolves without
# executing ``custom_components/filc/__init__.py`` (which imports Home Assistant).
_pkg = types.ModuleType("custom_components.filc")
_pkg.__path__ = [str(COMPONENT_DIR)]
sys.modules["custom_components.filc"] = _pkg

from custom_components.filc.api import _items  # noqa: E402


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
