"""Timely state refreshes and optional phone notifications for Filc.

Two jobs:
1. Refresh the coordinator exactly at lesson boundaries, so the current/next
   sensors and the ``in_lesson`` binary sensor flip on time even though the
   poll interval is coarse (5 minutes by default).
2. If a phone (a ``notify.mobile_app_*`` service) is selected in the options,
   send a reminder before the next lesson and a break summary when a lesson
   ends.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time

from . import schedule
from .coordinator import FilcDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class FilcNotifier:
    """Schedule boundary refreshes and optional notifications."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: FilcDataUpdateCoordinator,
        service: str | None,
        lead_minutes: int,
        on_break: bool,
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._service = service or None
        self._lead = timedelta(minutes=lead_minutes)
        self._on_break = on_break
        self._hu = (hass.config.language or "en").lower().startswith("hu")
        self._unsubs: list = []
        self._unsub_listener = None

    @property
    def enabled(self) -> bool:
        """Whether a phone is selected."""
        return bool(self._service)

    def async_setup(self) -> None:
        """Start listening for updates and schedule the first points."""
        self._unsub_listener = self.coordinator.async_add_listener(
            self._handle_update
        )
        self._reschedule()

    @callback
    def _handle_update(self) -> None:
        self._reschedule()

    def cancel(self) -> None:
        """Cancel timers and the coordinator listener."""
        if self._unsub_listener is not None:
            self._unsub_listener()
            self._unsub_listener = None
        self._cancel_timers()

    def _cancel_timers(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    def _reschedule(self) -> None:
        self._cancel_timers()
        if not self.coordinator.data:
            return

        now = schedule.now()
        current = self.coordinator.current()
        upcoming = self.coordinator.upcoming()

        # Flip the state sensors exactly at the next lesson's start.
        if upcoming is not None and upcoming.start > now:
            self._schedule_point(upcoming.start, self.coordinator.async_request_refresh)

        # Flip the state sensors at the end of the current lesson.
        if current is not None and current.end > now:
            self._schedule_point(current.end, self._handle_lesson_end)

        if not self.enabled:
            return

        # Reminder shortly before the next lesson.
        if upcoming is not None:
            when = upcoming.start - self._lead
            if when > now:
                lesson_id = upcoming.lesson.id
                self._schedule_point(when, lambda lid=lesson_id: self._notify_before(lid))

    @callback
    def _handle_lesson_end(self) -> None:
        self.hass.async_create_task(self.coordinator.async_request_refresh())
        if self.enabled and self._on_break:
            self.hass.async_create_task(self._notify_break())

    def _schedule_point(self, when, action) -> None:
        @callback
        def _fire(_now=None) -> None:
            self.hass.async_create_task(action())

        self._unsubs.append(async_track_point_in_time(self.hass, _fire, when))

    async def _notify_before(self, lesson_id: str) -> None:
        upcoming = self.coordinator.upcoming()
        if upcoming is None or upcoming.lesson.id != lesson_id:
            return
        subject = upcoming.lesson.subject or upcoming.lesson.subject_short or "Óra"
        room = f" · 📍 {upcoming.room}" if upcoming.room else ""
        teacher = f" · {upcoming.teacher}" if upcoming.teacher else ""
        minutes = int(self._lead.total_seconds() // 60)
        if self._hu:
            title = f"Következő óra {minutes} perc múlva"
            message = f"{subject}{room}{teacher} · kezdés {upcoming.start:%H:%M}"
        else:
            title = f"Next lesson in {minutes} minutes"
            message = f"{subject}{room}{teacher} · starts {upcoming.start:%H:%M}"
        await self._send(title, message)

    async def _notify_break(self) -> None:
        now = schedule.now()
        upcoming = self.coordinator.upcoming()
        if upcoming is None or upcoming.date != now.date():
            return
        subject = upcoming.lesson.subject or upcoming.lesson.subject_short or "Óra"
        room = f" · 📍 {upcoming.room}" if upcoming.room else ""
        if self._hu:
            title = "Szünet"
            message = f"Következő: {subject}{room} · {upcoming.start:%H:%M}"
        else:
            title = "Break"
            message = f"Next: {subject}{room} · {upcoming.start:%H:%M}"
        await self._send(title, message)

    async def _send(self, title: str, message: str) -> None:
        try:
            await self.hass.services.async_call(
                "notify",
                self._service,
                {"title": title, "message": message},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001 - a missing phone must not break the update loop
            _LOGGER.warning("Filc notification to %s failed: %s", self._service, err)
