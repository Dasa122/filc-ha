"""Switch platform for the Filc integration."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_LIVE_ACTIVITY, DEFAULT_LIVE_ACTIVITY
from .coordinator import FilcDataUpdateCoordinator
from .entity import FilcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Filc switches."""
    coordinator: FilcDataUpdateCoordinator = entry.runtime_data
    async_add_entities([FilcLiveActivitySwitch(coordinator, entry)])


class FilcLiveActivitySwitch(FilcEntity, SwitchEntity):
    """Turn the Live Activity on the selected phone on or off."""

    _attr_translation_key = "live_activity"
    _attr_icon = "mdi:cellphone-message"

    def __init__(self, coordinator: FilcDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{coordinator.cohort_id}_live_activity"

    @property
    def is_on(self) -> bool:
        """Whether the Live Activity is enabled."""
        data = {**self._entry.data, **self._entry.options}
        return bool(data.get(CONF_LIVE_ACTIVITY, DEFAULT_LIVE_ACTIVITY))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the Live Activity."""
        self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the Live Activity."""
        self._set(False)

    @callback
    def _set(self, enabled: bool) -> None:
        """Persist the option; the entry's update listener reloads the integration."""
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, CONF_LIVE_ACTIVITY: enabled}
        )
