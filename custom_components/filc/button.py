"""Button platform for the Filc integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import schedule
from .const import CONF_NOTIFY_SERVICE
from .coordinator import FilcDataUpdateCoordinator
from .entity import FilcEntity
from .messages import live_state


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Filc buttons."""
    coordinator: FilcDataUpdateCoordinator = entry.runtime_data
    async_add_entities([FilcTestLiveActionsButton(coordinator, entry)])


class FilcTestLiveActionsButton(FilcEntity, ButtonEntity):
    """Send the current live action to the selected phone and to the UI."""

    _attr_translation_key = "test_live_actions"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, coordinator: FilcDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{coordinator.cohort_id}_test_live_actions"

    async def async_press(self) -> None:
        data = {**self._entry.data, **self._entry.options}
        hu = (self.hass.config.language or "en").lower().startswith("hu")
        title, message = live_state(
            self.coordinator.current(),
            self.coordinator.upcoming(),
            schedule.today(),
            hu,
        )

        service = data.get(CONF_NOTIFY_SERVICE)
        if service:
            await self.hass.services.async_call(
                "notify",
                service,
                {"title": title, "message": message},
                blocking=False,
            )
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": f"filc_{self.coordinator.cohort_id}",
            },
            blocking=False,
        )
