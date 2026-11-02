"""Timely state refreshes, phone notifications and the Live Activity for Filc."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time

from . import schedule
from .coordinator import FilcDataUpdateCoordinator
from .messages import live_activity, nothing_today

_LOGGER = logging.getLogger(__name__)

# Fields copied from the pure live_activity() payload into the notify data block.
# No progress/progress_max on purpose: on iOS `progress` replaces `critical_text`,
# and we want the lesson name + room visible next to the timer.
_ACTIVITY_KEYS = ("critical_text", "chronometer", "when", "when_relative")


def activity_notify_data(payload: dict, tag: str) -> dict:
    """Build the companion-app data block for a Live Activity / Live Update."""
    data: dict = {
        "tag": tag,
        "live_update": True,
        "notification_icon": "mdi:school",
        "notification_icon_color": "#15ba81",
        "color": "#15ba81",
    }
    for key in _ACTIVITY_KEYS:
        if key in payload:
            data[key] = payload[key]
    return data


class FilcNotifier:
    """Schedule boundary refreshes, phone notifications and the Live Activity."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: FilcDataUpdateCoordinator,
        service: str | None,
        lead_minutes: int,
        on_break: bool,
        live_activity_enabled: bool = True,
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._service = service or None
        # kept only so the existing config-option keys still round-trip; the
        # reminder/break pushes are currently disabled.
        self._lead = timedelta(minutes=lead_minutes)
        self._on_break = on_break
        self._live_activity_enabled = live_activity_enabled
        self._hu = (hass.config.language or "en").lower().startswith("hu")
        self._tag = f"filc_{coordinator.cohort_id}"
        self._unsubs: list = []
        self._unsub_listener = None
        self._last_key: str | None = None
        # "an activity may be on the phone": seeded True so the first
        # reconciliation after a restart/reload always clears a leftover
        # activity. A redundant clear is harmless; a missed one is the bug.
        self._shown = True
        # Serialises every send so a stale in-flight update cannot land after
        # a clear and resurrect the activity.
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        """Whether a phone is selected."""
        return bool(self._service)

    def async_setup(self) -> None:
        """Start listening, schedule the boundaries and reconcile once.

        Always reconciles — even when disabled or no phone is selected — so a
        toggled-off activity or a leftover from a previous run gets cleared.
        """
        self._unsub_listener = self.coordinator.async_add_listener(
            self._handle_update
        )
        self._reschedule()
        self.hass.async_create_task(self._update_live_activity())

    @callback
    def _handle_update(self) -> None:
        self._reschedule()
        self.hass.async_create_task(self._update_live_activity())

    async def async_shutdown(self) -> None:
        """Clear any shown activity, then stop the listener and timers.

        Idempotent: a second call sees ``_shown`` False, an already-removed
        listener and no timers, so it sends nothing and raises nothing.
        """
        async with self._lock:
            if self._shown and self.enabled:
                try:
                    await self._send_raw(
                        {"message": "clear_notification", "data": {"tag": self._tag}}
                    )
                except Exception as err:  # noqa: BLE001 - best effort on unload
                    _LOGGER.warning("Filc Live Activity clear failed: %s", err)
                self._shown = False
            self._last_key = None
        if self._unsub_listener is not None:
            self._unsub_listener()
            self._unsub_listener = None
        self._cancel_timers()

    def _cancel_timers(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    def _state_key(self, now, current, upcoming) -> str:
        """A key that changes only at lesson boundaries (dedupes pushes)."""
        return "|".join(
            [
                now.date().isoformat(),
                current.lesson.id if current else "-",
                upcoming.lesson.id if upcoming else "-",
            ]
        )

    def _reschedule(self) -> None:
        self._cancel_timers()
        if not self.coordinator.data:
            return

        now = schedule.now()
        current = self.coordinator.current()
        upcoming = self.coordinator.upcoming()

        # Refresh exactly at the next lesson start / current lesson end. The
        # refresh triggers _handle_update, which pushes the Live Activity update.
        if upcoming is not None and upcoming.start > now:
            self._schedule_point(upcoming.start, self._handle_lesson_start)
        if current is not None and current.end > now:
            self._schedule_point(current.end, self._handle_lesson_end)

    @callback
    def _handle_lesson_start(self) -> None:
        # async_refresh is immediate; async_request_refresh is debounced and
        # could swallow a boundary, leaving a stale activity on the phone.
        self.hass.async_create_task(self.coordinator.async_refresh())

    @callback
    def _handle_lesson_end(self) -> None:
        self.hass.async_create_task(self.coordinator.async_refresh())

    def _schedule_point(self, when, action) -> None:
        @callback
        def _fire(_now=None) -> None:
            self.hass.async_create_task(action())

        self._unsubs.append(async_track_point_in_time(self.hass, _fire, when))

    async def _update_live_activity(self) -> None:
        """Start, update or end the Live Activity for the current state."""
        async with self._lock:
            now = schedule.now()
            current = self.coordinator.current()
            upcoming = self.coordinator.upcoming()

            # Disabled, no phone, or nothing left today: nothing can be showing,
            # and any activity already on a phone must be cleared (once).
            if (
                not self.enabled
                or not self._live_activity_enabled
                or nothing_today(current, upcoming, now)
            ):
                if self.enabled and self._shown:
                    await self._send_raw(
                        {"message": "clear_notification", "data": {"tag": self._tag}}
                    )
                self._shown = False
                self._last_key = None
                return

            key = self._state_key(now, current, upcoming)
            if key == self._last_key:
                return

            payload = live_activity(current, upcoming, now, self._hu)
            await self._send_raw(
                {
                    "title": payload["title"],
                    "message": payload["message"],
                    "data": activity_notify_data(payload, self._tag),
                }
            )
            self._last_key = key
            self._shown = True

    async def _send_raw(self, data: dict) -> None:
        """Send one notify payload; a missing/failing service logs, never raises."""
        try:
            await self.hass.services.async_call(
                "notify", self._service, data, blocking=True
            )
        except Exception as err:  # noqa: BLE001 - a missing phone must not break the update loop
            _LOGGER.warning(
                "Filc notification to %s failed: %s", self._service, err
            )
