"""Async HTTP client for the Filc (Chronos) API."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import API_PREFIX

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=15)


def _items(payload: Any) -> list:
    """Unwrap a list or a ``{"items": [...]}`` envelope into a list."""
    if isinstance(payload, dict):
        return payload.get("items") or []
    if isinstance(payload, list):
        return payload
    return []


def parse_door_target(target: str) -> tuple[str, str]:
    """Split a stored ``cardId|deviceId`` door target."""
    card_id, _, device_id = (target or "").partition("|")
    return card_id, device_id


class FilcApiError(Exception):
    """Raised when the Filc API returns an error."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class FilcApi:
    """Thin wrapper around the Filc endpoints used by the integration."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._api_key = api_key or None

    @property
    def base_url(self) -> str:
        return self._base

    def _url(self, path: str) -> str:
        return f"{self._base}{API_PREFIX}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.get(
                self._url(path),
                headers=self._headers(),
                params=params,
                timeout=TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise FilcApiError("Unauthorized", resp.status)
                if resp.status >= 400:
                    raise FilcApiError(
                        f"HTTP {resp.status} for {path}", resp.status
                    )
                try:
                    payload = await resp.json()
                except ValueError as err:
                    raise FilcApiError(f"Malformed response for {path}") from err
        except aiohttp.ClientError as err:
            raise FilcApiError(f"Connection error: {err}") from err

        return payload

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            async with self._session.post(
                self._url(path),
                headers=self._headers(),
                json=payload,
                timeout=TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise FilcApiError("Unauthorized", resp.status)
                if resp.status >= 400:
                    detail = ""
                    try:
                        body = await resp.json()
                    except ValueError:
                        body = None
                    if isinstance(body, dict):
                        detail = ": ".join(
                            str(part)
                            for part in (body.get("code"), body.get("message"))
                            if part
                        )
                    raise FilcApiError(
                        detail or f"HTTP {resp.status} for {path}", resp.status
                    )
                try:
                    return await resp.json()
                except ValueError:
                    return None
        except aiohttp.ClientError as err:
            raise FilcApiError(f"Connection error: {err}") from err

    async def ping(self) -> Any:
        """Health check."""
        return await self._get("/ping")

    async def latest_timetable(self) -> dict:
        """Return the currently active timetable."""
        return await self._get("/timetable/timetables/latestValid")

    async def cohorts(self, timetable_id: str) -> list[dict]:
        """Return the cohorts (classes) of a timetable."""
        return _items(
            await self._get(f"/timetable/cohorts/getAllForTimetable/{timetable_id}")
        )

    async def periods(self) -> list[dict]:
        """Return the period (lesson bell) definitions."""
        return _items(await self._get("/timetable/periods/getAll"))

    async def lessons(self, cohort_id: str, timetable_id: str) -> list[dict]:
        """Return the weekly lesson grid of a cohort."""
        return _items(
            await self._get(
                f"/timetable/lessons/getForCohort/{cohort_id}",
                params={"timetableId": timetable_id},
            )
        )

    async def substitutions(self, cohort_id: str) -> list[dict]:
        """Return the relevant (future) substitutions of a cohort."""
        data = await self._get(f"/timetable/substitutions/cohort/{cohort_id}") or {}
        return data.get("substitutions", []) if isinstance(data, dict) else []

    async def moved_lessons(self, cohort_id: str) -> list[dict]:
        """Return the relevant moved lessons of a cohort."""
        return _items(
            await self._get(f"/timetable/movedLessons/cohort/{cohort_id}/relevant")
        )

    async def groups(self, cohort_id: str) -> list[dict]:
        """Return the groups of a cohort.

        With a valid API key the ``selected`` flag marks the signed-in user's
        own group choices (as picked in the live Filc app).
        """
        return _items(await self._get(f"/timetable/groups/getForCohort/{cohort_id}"))

    async def validate_key(self) -> bool:
        """Return True when the configured API key is accepted.

        A 403 means the key authenticated but the account lacks the
        ``usersRead`` permission, so it is still a valid key.
        """
        try:
            await self._get("/users")
        except FilcApiError as err:
            if err.status == 401:
                return False
            if err.status == 403:
                return True
            raise
        return True

    async def cards(self) -> list[dict]:
        """Return the door cards owned by the API-key user."""
        return _items(await self._get("/doorlock/self/cards"))

    async def activate_card(
        self, card_id: str, device_id: str | None = None
    ) -> Any:
        """Publish an unlock request for one of the user's cards."""
        payload = {"deviceId": device_id} if device_id else {}
        return await self._post(
            f"/doorlock/self/cards/{quote(card_id, safe='')}/activate", payload
        )
