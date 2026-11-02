"""Structural guard: no module under custom_components/filc may build ZoneInfo.

The school time zone is resolved once, off the Home Assistant event loop, in
async_setup_entry and handed down through the coordinator. A module that
imports `zoneinfo` or constructs `ZoneInfo(...)` re-introduces blocking file
I/O on the event loop, so this test fails if any component module does either.
"""

import ast
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "filc"


def _zoneinfo_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "zoneinfo" for a in node.names):
            violations.append(f"import zoneinfo (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom) and node.module == "zoneinfo":
            violations.append(f"from zoneinfo import ... (line {node.lineno})")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ZoneInfo"
        ):
            violations.append(f"ZoneInfo(...) (line {node.lineno})")
    return violations


def test_no_zoneinfo_in_component():
    offenders = {
        path.name: _zoneinfo_violations(path)
        for path in COMPONENT.glob("*.py")
        if _zoneinfo_violations(path)
    }
    assert not offenders, f"ZoneInfo usage in component modules: {offenders}"
