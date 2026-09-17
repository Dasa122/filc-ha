"""Diagnostics support for the Filc integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import schedule
from .const import CONF_API_KEY
from .models import Occurrence

TO_REDACT = {CONF_API_KEY}


def _occurrence(occ: Occurrence | None) -> dict[str, Any] | None:
    if occ is None:
        return None
    return {
        "subject": occ.lesson.subject or occ.lesson.subject_short or None,
        "room": occ.room,
        "teacher": occ.teacher,
        "period": occ.lesson.period_no,
        "date": occ.date.isoformat(),
        "start": occ.start.isoformat(),
        "end": occ.end.isoformat(),
        "moved": occ.moved,
        "substituted": occ.substituted,
        "cancelled": occ.cancelled,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "now": schedule.now().isoformat(),
        "current": _occurrence(coordinator.current()),
        "upcoming": _occurrence(coordinator.upcoming()),
        "counts": {
            "lessons": len(data.lessons) if data else 0,
            "substitutions": len(data.substitutions) if data else 0,
            "moved_lessons": len(data.moved_lessons) if data else 0,
        },
        "timetable": data.timetable if data else None,
        "selected_group_ids": sorted(data.selected_group_ids) if data else [],
    }
