"""DataUpdateCoordinator for the Filc integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import schedule
from .api import FilcApi, FilcApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import Lesson, Occurrence, ScheduleData

_LOGGER = logging.getLogger(__name__)


class FilcDataUpdateCoordinator(DataUpdateCoordinator[ScheduleData]):
    """Fetch and hold the cohort's schedule and its daily overrides."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FilcApi,
        cohort_id: str,
        cohort_name: str,
        timetable_id: str | None,
        selected_group_ids: list[str] | None,
        scan_interval: int | None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {cohort_name}",
            update_interval=timedelta(
                seconds=scan_interval or DEFAULT_SCAN_INTERVAL
            ),
        )
        self.api = api
        self.cohort_id = cohort_id
        self.cohort_name = cohort_name
        self.timetable_id = timetable_id
        self.selected_group_ids = set(selected_group_ids or [])
        self.base_url = api.base_url

    async def _async_update_data(self) -> ScheduleData:
        try:
            timetable = await self.api.latest_timetable()
        except FilcApiError as err:
            raise UpdateFailed(f"Timetable fetch failed: {err}") from err

        timetable_id = (timetable or {}).get("id") or self.timetable_id
        if not timetable_id:
            raise UpdateFailed("No active timetable available")
        self.timetable_id = timetable_id

        try:
            lessons_raw, periods, substitutions, moved = await asyncio.gather(
                self.api.lessons(self.cohort_id, timetable_id),
                self.api.periods(),
                self.api.substitutions(self.cohort_id),
                self.api.moved_lessons(self.cohort_id),
            )
        except FilcApiError as err:
            raise UpdateFailed(f"Schedule fetch failed: {err}") from err

        return ScheduleData(
            lessons=[Lesson.from_raw(raw) for raw in lessons_raw],
            periods=periods or [],
            substitutions=substitutions or [],
            moved_lessons=moved or [],
            selected_group_ids=self.selected_group_ids,
            timetable=timetable or {},
        )

    def current(self) -> Occurrence | None:
        """Return the lesson in progress right now, if any."""
        data = self.data
        if not data:
            return None
        return schedule.current_occurrence(
            schedule.now(),
            data.lessons,
            data.selected_group_ids,
            data.moved_lessons,
            data.substitutions,
        )

    def upcoming(self) -> Occurrence | None:
        """Return the next lesson after now (scans forward across days)."""
        data = self.data
        if not data:
            return None
        return schedule.next_occurrence(
            schedule.now(),
            data.lessons,
            data.selected_group_ids,
            data.moved_lessons,
            data.substitutions,
        )
