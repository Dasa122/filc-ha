"""Sensor platform for the Filc integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from . import schedule
from .entity import FilcEntity

BREAK_STATE = "Szünet"


class _FilcSensor(FilcEntity, SensorEntity):
    """Base class assigning a stable unique id per cohort."""

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.cohort_id}_{key}"


class FilcCurrentLessonSensor(_FilcSensor):
    """Subject of the lesson currently in progress, else 'Szünet'."""

    _attr_translation_key = "current_lesson"
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "current_lesson")

    @property
    def native_value(self) -> str | None:
        current = self.coordinator.current()
        if current:
            return current.lesson.subject or current.lesson.subject_short or "Óra"

        upcoming = self.coordinator.upcoming()
        if upcoming and upcoming.date == schedule.today():
            return BREAK_STATE
        return None

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        current = self.coordinator.current()
        upcoming = self.coordinator.upcoming()
        if current:
            attrs.update(
                subject=current.lesson.subject or None,
                room=current.room,
                teacher=current.teacher,
                period=current.lesson.period_no,
                starts_at=current.start.isoformat(),
                ends_at=current.end.isoformat(),
            )
        if upcoming:
            attrs.update(
                next_subject=upcoming.lesson.subject or None,
                next_room=upcoming.room,
                next_starts_at=upcoming.start.isoformat(),
            )
        return attrs


class FilcNextLessonSensor(_FilcSensor):
    """Subject of the next lesson."""

    _attr_translation_key = "next_lesson"
    _attr_icon = "mdi:book-clock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_lesson")

    @property
    def native_value(self) -> str | None:
        upcoming = self.coordinator.upcoming()
        if not upcoming:
            return None
        return upcoming.lesson.subject or upcoming.lesson.subject_short or "Óra"

    @property
    def extra_state_attributes(self) -> dict:
        upcoming = self.coordinator.upcoming()
        if not upcoming:
            return {}
        return {
            "subject": upcoming.lesson.subject or None,
            "room": upcoming.room,
            "teacher": upcoming.teacher,
            "period": upcoming.lesson.period_no,
            "starts_at": upcoming.start.isoformat(),
            "date": upcoming.date.isoformat(),
        }


class FilcCurrentLessonEndSensor(_FilcSensor):
    """Timestamp when the current lesson ends (drives the live countdown)."""

    _attr_translation_key = "current_lesson_end"
    _attr_icon = "mdi:timer-sand-complete"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "current_lesson_end")

    @property
    def native_value(self):
        current = self.coordinator.current()
        return current.end if current else None


class FilcNextLessonStartSensor(_FilcSensor):
    """Timestamp when the next lesson starts (drives the live countdown)."""

    _attr_translation_key = "next_lesson_start"
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_lesson_start")

    @property
    def native_value(self):
        upcoming = self.coordinator.upcoming()
        return upcoming.start if upcoming else None
