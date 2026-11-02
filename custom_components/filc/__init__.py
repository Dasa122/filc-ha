"""The Filc integration: your school timetable in Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import FilcApi
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_COHORT_ID,
    CONF_COHORT_NAME,
    CONF_LIVE_ACTIVITY,
    CONF_NOTIFY_LEAD,
    CONF_NOTIFY_ON_BREAK,
    CONF_NOTIFY_SERVICE,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_GROUP_IDS,
    CONF_TIMETABLE_ID,
    DEFAULT_LIVE_ACTIVITY,
    DEFAULT_NOTIFY_LEAD,
    DEFAULT_NOTIFY_ON_BREAK,
    DEFAULT_SCAN_INTERVAL,
    SCHOOL_TZ,
)
from .coordinator import FilcDataUpdateCoordinator
from .notifications import FilcNotifier

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Filc from a config entry."""
    data = {**entry.data, **entry.options}

    session = async_get_clientsession(hass)
    api = FilcApi(session, data[CONF_BASE_URL], data.get(CONF_API_KEY))

    tz = await dt_util.async_get_time_zone(SCHOOL_TZ)
    if tz is None:
        raise ConfigEntryNotReady("Time zone database unavailable")

    coordinator = FilcDataUpdateCoordinator(
        hass,
        api,
        data[CONF_COHORT_ID],
        data[CONF_COHORT_NAME],
        data.get(CONF_TIMETABLE_ID),
        data.get(CONF_SELECTED_GROUP_IDS),
        data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        tz,
    )

    # Raises ConfigEntryNotReady itself when the first refresh fails.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    notifier = FilcNotifier(
        hass,
        coordinator,
        data.get(CONF_NOTIFY_SERVICE),
        data.get(CONF_NOTIFY_LEAD, DEFAULT_NOTIFY_LEAD),
        data.get(CONF_NOTIFY_ON_BREAK, DEFAULT_NOTIFY_ON_BREAK),
        data.get(CONF_LIVE_ACTIVITY, DEFAULT_LIVE_ACTIVITY),
    )
    notifier.async_setup()
    entry.async_on_unload(notifier.async_shutdown)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the options (class, groups, interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)
