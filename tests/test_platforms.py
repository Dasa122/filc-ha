"""Structural guard: every entity platform must define async_setup_entry.

A platform module without async_setup_entry is silently skipped by Home
Assistant, so the entities never appear. This caught a real bug where the
calendar, sensors and binary sensor were missing while only the button loaded.
"""

import ast
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "filc"
PLATFORMS = ["calendar.py", "sensor.py", "binary_sensor.py", "button.py"]


def _defines_async_setup_entry(path: Path) -> bool:
    tree = ast.parse(path.read_text())
    return any(
        isinstance(node, ast.AsyncFunctionDef) and node.name == "async_setup_entry"
        for node in tree.body
    )


def test_platforms_define_async_setup_entry():
    missing = [name for name in PLATFORMS if not _defines_async_setup_entry(COMPONENT / name)]
    assert not missing, f"missing async_setup_entry in: {missing}"
