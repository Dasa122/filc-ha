"""Sensor platform for the Filc integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import messages, schedule
from .coordinator import FilcDataUpdateCoordinator
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
            name = current.lesson.subject or None
            attrs.update(
                current_lesson=name,
                current_room=current.room,
                current_teacher=current.teacher,
                subject=name,
                room=current.room,
                teacher=current.teacher,
                period=current.lesson.period_no,
                starts_at=current.start.isoformat(),
                ends_at=current.end.isoformat(),
            )
        if upcoming:
            attrs.update(
                next_lesson=upcoming.lesson.subject or None,
                next_room=upcoming.room,
                next_subject=upcoming.lesson.subject or None,
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
            "lesson": upcoming.lesson.subject or None,
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


class FilcCurrentRoomSensor(_FilcSensor):
    """Room of the lesson currently in progress."""

    _attr_translation_key = "current_room"
    _attr_icon = "mdi:door"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "current_room")

    @property
    def native_value(self) -> str | None:
        current = self.coordinator.current()
        return current.room if current else None

    @property
    def extra_state_attributes(self) -> dict:
        current = self.coordinator.current()
        if not current:
            return {}
        return {
            "lesson": current.lesson.subject or None,
            "teacher": current.teacher,
            "ends_at": current.end.isoformat(),
        }


class FilcNextRoomSensor(_FilcSensor):
    """Room of the next lesson."""

    _attr_translation_key = "next_room"
    _attr_icon = "mdi:door-open"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_room")

    @property
    def native_value(self) -> str | None:
        upcoming = self.coordinator.upcoming()
        return upcoming.room if upcoming else None

    @property
    def extra_state_attributes(self) -> dict:
        upcoming = self.coordinator.upcoming()
        if not upcoming:
            return {}
        return {
            "lesson": upcoming.lesson.subject or None,
            "teacher": upcoming.teacher,
            "starts_at": upcoming.start.isoformat(),
            "date": upcoming.date.isoformat(),
        }


class FilcCurrentTeacherSensor(_FilcSensor):
    """Full name of the teacher of the lesson currently in progress."""

    _attr_translation_key = "current_teacher"
    _attr_icon = "mdi:account-tie"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "current_teacher")

    @property
    def native_value(self) -> str | None:
        current = self.coordinator.current()
        return current.teacher if current else None

    @property
    def extra_state_attributes(self) -> dict:
        current = self.coordinator.current()
        if not current:
            return {}
        return {
            "teacher_short": current.teacher_short,
            "subject": current.lesson.subject or None,
            "room": current.room,
            "starts_at": current.start.isoformat(),
            "ends_at": current.end.isoformat(),
        }


class FilcNextTeacherSensor(_FilcSensor):
    """Full name of the teacher of the next lesson."""

    _attr_translation_key = "next_teacher"
    _attr_icon = "mdi:account-tie-outline"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_teacher")

    @property
    def native_value(self) -> str | None:
        upcoming = self.coordinator.upcoming()
        return upcoming.teacher if upcoming else None

    @property
    def extra_state_attributes(self) -> dict:
        upcoming = self.coordinator.upcoming()
        if not upcoming:
            return {}
        return {
            "teacher_short": upcoming.teacher_short,
            "subject": upcoming.lesson.subject or None,
            "room": upcoming.room,
            "starts_at": upcoming.start.isoformat(),
            "date": upcoming.date.isoformat(),
        }


class FilcCurrentPeriodSensor(_FilcSensor):
    """Period number of the lesson currently in progress."""

    _attr_translation_key = "current_period"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "current_period")

    @property
    def native_value(self) -> int | None:
        current = self.coordinator.current()
        return current.lesson.period_no if current else None

    @property
    def extra_state_attributes(self) -> dict:
        current = self.coordinator.current()
        if not current:
            return {}
        return {
            "subject": current.lesson.subject or None,
            "starts_at": current.start.isoformat(),
            "ends_at": current.end.isoformat(),
        }


class FilcNextPeriodSensor(_FilcSensor):
    """Period number of the next lesson."""

    _attr_translation_key = "next_period"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_period")

    @property
    def native_value(self) -> int | None:
        upcoming = self.coordinator.upcoming()
        return upcoming.lesson.period_no if upcoming else None

    @property
    def extra_state_attributes(self) -> dict:
        upcoming = self.coordinator.upcoming()
        if not upcoming:
            return {}
        return {
            "subject": upcoming.lesson.subject or None,
            "starts_at": upcoming.start.isoformat(),
            "date": upcoming.date.isoformat(),
        }


class FilcCurrentLessonStartSensor(_FilcSensor):
    """Timestamp when the current lesson started."""

    _attr_translation_key = "current_lesson_start"
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "current_lesson_start")

    @property
    def native_value(self):
        current = self.coordinator.current()
        return current.start if current else None


class FilcNextLessonEndSensor(_FilcSensor):
    """Timestamp when the next lesson ends."""

    _attr_translation_key = "next_lesson_end"
    _attr_icon = "mdi:timer-sand-complete"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_lesson_end")

    @property
    def native_value(self):
        upcoming = self.coordinator.upcoming()
        return upcoming.end if upcoming else None


class FilcSchoolStateSensor(_FilcSensor):
    """One-word school state: in lesson, break, no more today, or no lessons."""

    _attr_translation_key = "school_state"
    _attr_icon = "mdi:school"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "school_state")

    @property
    def native_value(self) -> str:
        hu = (self.hass.config.language or "en").lower().startswith("hu")
        return messages.school_state(
            self.coordinator.current(),
            self.coordinator.upcoming(),
            schedule.today(),
            hu,
        )


class FilcNextDayFirstLessonSensor(_FilcSensor):
    """Timestamp of the first lesson on the next school day that has lessons."""

    _attr_translation_key = "next_day_first_lesson"
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_day_first_lesson")

    @property
    def native_value(self):
        occ = self.coordinator.first_lesson_after_day()
        return occ.start if occ else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Filc sensors."""
    coordinator: FilcDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        [
            FilcCurrentLessonSensor(coordinator),
            FilcNextLessonSensor(coordinator),
            FilcCurrentRoomSensor(coordinator),
            FilcNextRoomSensor(coordinator),
            FilcCurrentLessonEndSensor(coordinator),
            FilcNextLessonStartSensor(coordinator),
            FilcCurrentTeacherSensor(coordinator),
            FilcNextTeacherSensor(coordinator),
            FilcCurrentPeriodSensor(coordinator),
            FilcNextPeriodSensor(coordinator),
            FilcCurrentLessonStartSensor(coordinator),
            FilcNextLessonEndSensor(coordinator),
            FilcSchoolStateSensor(coordinator),
            FilcNextDayFirstLessonSensor(coordinator),
        ]
    )
