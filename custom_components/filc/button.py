"""Button platform for the Filc integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import schedule
from .api import FilcApiError, parse_door_target
from .const import CONF_DOOR_TARGET, CONF_NOTIFY_SERVICE
from .coordinator import FilcDataUpdateCoordinator
from .entity import FilcEntity
from .messages import live_activity
from .notifications import activity_notify_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Filc buttons."""
    coordinator: FilcDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        [
            FilcTestLiveActionsButton(coordinator, entry),
            FilcOpenDoorButton(coordinator, entry),
        ]
    )


class FilcTestLiveActionsButton(FilcEntity, ButtonEntity):
    """Send the current live action to the selected phone."""

    _attr_translation_key = "test_live_actions"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, coordinator: FilcDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{coordinator.cohort_id}_test_live_actions"

    async def async_press(self) -> None:
        data = {**self._entry.data, **self._entry.options}
        hu = (self.hass.config.language or "en").lower().startswith("hu")
        current = self.coordinator.current()
        upcoming = self.coordinator.upcoming()
        now = schedule.now(self.coordinator.tz)

        service = data.get(CONF_NOTIFY_SERVICE)
        if not service:
            _LOGGER.warning("No notification phone configured; cannot send the live action")
            return

        payload = live_activity(current, upcoming, now, hu)
        await self.hass.services.async_call(
            "notify",
            service,
            {
                "title": payload["title"],
                "message": payload["message"],
                "data": activity_notify_data(
                    payload, f"filc_{self.coordinator.cohort_id}"
                ),
            },
            blocking=False,
        )


class FilcOpenDoorButton(FilcEntity, ButtonEntity):
    """Publish an unlock request for the selected card/reader."""

    _attr_translation_key = "open_door"
    _attr_icon = "mdi:door-open"

    def __init__(self, coordinator: FilcDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{coordinator.cohort_id}_open_door"

    async def async_press(self) -> None:
        data = {**self._entry.data, **self._entry.options}
        card_id, device_id = parse_door_target(data.get(CONF_DOOR_TARGET) or "")
        if not card_id:
            _LOGGER.warning("No door card configured; cannot open the door")
            return
        try:
            await self.coordinator.api.activate_card(card_id, device_id or None)
        except FilcApiError as err:
            raise HomeAssistantError(f"Filc door request failed: {err}") from err
