"""Calendar platform for the Filc integration."""

from __future__ import annotations

from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from . import schedule
from .entity import FilcEntity
from .models import Occurrence


def _summary(occ: Occurrence) -> str:
    return occ.lesson.subject or occ.lesson.subject_short or "Óra"


def _description(occ: Occurrence) -> str:
    parts = [f"{occ.lesson.period_no}. óra"]
    if occ.teacher:
        parts.append(occ.teacher)
    if occ.room:
        parts.append(occ.room)
    if occ.substituted:
        parts.append("helyettesítés")
    if occ.moved:
        parts.append("teremcsere / áthelyezés")
    if occ.cancelled:
        parts.append("ELMARAD")
    return " · ".join(parts)


def _to_event(occ: Occurrence) -> CalendarEvent:
    return CalendarEvent(
        summary=_summary(occ),
        start=occ.start,
        end=occ.end,
        location=occ.room,
        description=_description(occ),
    )


class FilcCalendar(FilcEntity, CalendarEntity):
    """The cohort's timetable as a Home Assistant calendar."""

    _attr_translation_key = "calendar"
    _attr_icon = "mdi:school"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next lesson."""
        occ = self.coordinator.current() or self.coordinator.upcoming()
        return _to_event(occ) if occ else None

    async def async_get_events(self, hass, start_date, end_date) -> list[CalendarEvent]:
        """Return every lesson between two datetimes."""
        data = self.coordinator.data
        if not data:
            return []

        occurrences = schedule.expand_range(
            start_date.date(),
            end_date.date(),
            data.lessons,
            data.selected_group_ids,
            data.moved_lessons,
            data.substitutions,
        )
        return [
            _to_event(occ)
            for occ in occurrences
            if occ.start < end_date and occ.end > start_date
        ]
