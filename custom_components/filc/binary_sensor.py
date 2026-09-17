"""Binary sensor platform for the Filc integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FilcDataUpdateCoordinator
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Filc binary sensor."""
    coordinator: FilcDataUpdateCoordinator = entry.runtime_data
    async_add_entities([FilcInLessonBinarySensor(coordinator)])
