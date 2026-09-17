"""Shared base entity for the Filc integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FilcDataUpdateCoordinator


class FilcEntity(CoordinatorEntity[FilcDataUpdateCoordinator]):
    """Base class binding every Filc entity to the cohort's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FilcDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.cohort_id)},
            name=f"Filc {coordinator.cohort_name}",
            manufacturer="Filc",
            model="Órarend",
            configuration_url=coordinator.base_url,
        )
