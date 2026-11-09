"""Structural guard: boundary timers must call their callback directly.

`async_track_point_in_time` callbacks run in the event loop; the actions passed
to `_schedule_point` are plain `@callback` functions that create their own
refresh task and return None. Wrapping them in `async_create_task(...)` raises
"a coroutine was expected, got None" at every lesson boundary.
"""

import ast
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "filc"


def _fire_body() -> list[ast.stmt]:
    tree = ast.parse((COMPONENT / "notifications.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_fire":
            return node.body
    raise AssertionError("_fire not found in notifications.py")


def test_boundary_callback_is_called_directly():
    calls = [
        node
        for stmt in _fire_body()
        for node in ast.walk(stmt)
        if isinstance(node, ast.Call)
    ]
    names = [
        call.func.id
        for call in calls
        if isinstance(call.func, ast.Name)
    ]
    # The only call in _fire must be action(); no async_create_task(action()).
    assert names == ["action"], names
    assert not any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "async_create_task"
        for call in calls
    )
