"""Binary sensor platform for the Filc integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import FilcEntity


class FilcInLessonBinarySensor(FilcEntity, BinarySensorEntity):
    """On while a lesson is in progress (handy for phone automations)."""

    _attr_translation_key = "in_lesson"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_icon = "mdi:account-school"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.cohort_id}_in_lesson"

    @property
    def is_on(self) -> bool:
        return self.coordinator.current() is not None
