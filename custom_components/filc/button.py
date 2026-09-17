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
from .messages import live_activity, live_state


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
        current = self.coordinator.current()
        upcoming = self.coordinator.upcoming()
        now = schedule.now()

        title, message = live_state(current, upcoming, now.date(), hu)

        service = data.get(CONF_NOTIFY_SERVICE)
        if service:
            payload = live_activity(current, upcoming, now, hu)
            notify_data: dict = {
                "tag": f"filc_{self.coordinator.cohort_id}",
                "live_update": True,
                "notification_icon": "mdi:school",
                "notification_icon_color": "#15ba81",
                "color": "#15ba81",
            }
            for key in (
                "chronometer",
                "when",
                "when_relative",
                "progress",
                "progress_max",
            ):
                if key in payload:
                    notify_data[key] = payload[key]
            await self.hass.services.async_call(
                "notify",
                service,
                {
                    "title": payload["title"],
                    "message": payload["message"],
                    "data": notify_data,
                },
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
