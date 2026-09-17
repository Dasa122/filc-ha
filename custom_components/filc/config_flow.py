"""Config and options flow for the Filc integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .api import FilcApi, FilcApiError
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_COHORT_ID,
    CONF_COHORT_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_GROUP_IDS,
    CONF_TIMETABLE_ID,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _divisions(groups: list[dict]) -> dict[str, dict]:
    """Group the raw groups payload by division tag, with unique field keys."""
    divisions: dict[str, dict] = {}
    for group in groups or []:
        tag = group.get("divisionTag")
        if not tag:
            continue
        entry = divisions.setdefault(
            tag,
            {
                "label": group.get("divisionLabel") or group.get("name") or tag,
                "options": [],
            },
        )
        entry["options"].append(
            selector.SelectOptionDict(
                value=group["id"], label=group.get("name") or group["id"]
            )
        )

    seen: set[str] = set()
    for tag, info in divisions.items():
        key = slugify(info["label"]) or f"division_{tag}"
        if key in seen:
            key = f"{key}_{tag}"
        seen.add(key)
        info["key"] = key
    return divisions


def _group_schema(
    divisions: dict[str, dict], selected_ids: set[str]
) -> vol.Schema:
    """Build one dropdown per division, defaulting to the user's own group."""
    fields: dict = {}
    for info in divisions.values():
        options = [
            selector.SelectOptionDict(value="none", label="Nem érintett")
        ] + info["options"]
        default = "none"
        for option in info["options"]:
            if option["value"] in selected_ids:
                default = option["value"]
                break
        fields[vol.Optional(info["key"], default=default)] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        )
    return vol.Schema(fields)


def _picked_groups(divisions: dict[str, dict], user_input: dict) -> list[str]:
    picked: list[str] = []
    for info in divisions.values():
        value = user_input.get(info["key"])
        if value and value != "none":
            picked.append(value)
    return picked


class FilcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of a Filc class."""

    VERSION = 1

    def __init__(self) -> None:
        self._api: FilcApi | None = None
        self._base_url = DEFAULT_BASE_URL
        self._api_key: str | None = None
        self._timetable: dict | None = None
        self._cohort_id: str | None = None
        self._cohort_name: str | None = None
        self._cohorts: dict[str, str] = {}

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            self._base_url = user_input[CONF_BASE_URL].rstrip("/")
            self._api_key = user_input.get(CONF_API_KEY) or None
            api = FilcApi(
                async_get_clientsession(self.hass), self._base_url, self._api_key
            )
            try:
                await api.ping()
                if self._api_key and not await api.validate_key():
                    errors["base"] = "invalid_auth"
                else:
                    self._api = api
                    return await self.async_step_class()
            except FilcApiError:
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=self._base_url): str,
                vol.Optional(CONF_API_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_class(self, user_input=None):
        if self._api is None:
            return self.async_abort(reason="cannot_connect")
        if user_input is not None:
            self._cohort_id = user_input[CONF_COHORT_ID]
            self._cohort_name = self._cohorts.get(self._cohort_id, "Filc")
            await self.async_set_unique_id(self._cohort_id)
            self._abort_if_unique_id_configured()
            return await self.async_step_groups()

        try:
            self._timetable = await self._api.latest_timetable()
            cohorts = await self._api.cohorts(self._timetable["id"])
        except (FilcApiError, KeyError, TypeError) as err:
            _LOGGER.error("Failed to load cohorts: %s", err)
            return self.async_abort(reason="cannot_connect")

        self._cohorts = {c["id"]: c["name"] for c in cohorts}
        options = [
            selector.SelectOptionDict(value=c["id"], label=c["name"])
            for c in cohorts
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_COHORT_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="class", data_schema=schema)

    async def async_step_groups(self, user_input=None):
        if self._api is None or self._cohort_id is None:
            return self.async_abort(reason="cannot_connect")
        try:
            groups = await self._api.groups(self._cohort_id)
        except FilcApiError:
            return self.async_abort(reason="cannot_connect")

        divisions = _divisions(groups)
        if not divisions:
            return self._create_entry([])

        if user_input is not None:
            return self._create_entry(_picked_groups(divisions, user_input))

        selected = {g["id"] for g in groups if g.get("selected")}
        return self.async_show_form(
            step_id="groups",
            data_schema=_group_schema(divisions, selected),
        )

    def _create_entry(self, selected_group_ids: list[str]):
        return self.async_create_entry(
            title=self._cohort_name or "Filc",
            data={
                CONF_BASE_URL: self._base_url,
                CONF_API_KEY: self._api_key,
                CONF_COHORT_ID: self._cohort_id,
                CONF_COHORT_NAME: self._cohort_name,
                CONF_TIMETABLE_ID: (self._timetable or {}).get("id"),
                CONF_SELECTED_GROUP_IDS: selected_group_ids,
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return FilcOptionsFlow()


class FilcOptionsFlow(config_entries.OptionsFlow):
    """Change the class, groups and refresh interval."""

    _api: FilcApi | None = None
    _timetable: dict | None = None
    _cohort_id: str | None = None
    _cohort_name: str | None = None
    _cohorts: dict[str, str] = {}
    _interval: int = DEFAULT_SCAN_INTERVAL

    async def async_step_init(self, user_input=None):
        entry = self.config_entry
        data = {**entry.data, **entry.options}
        api = FilcApi(
            async_get_clientsession(self.hass),
            data[CONF_BASE_URL],
            data.get(CONF_API_KEY),
        )
        try:
            self._timetable = await api.latest_timetable()
            cohorts = await api.cohorts(self._timetable["id"])
        except (FilcApiError, KeyError, TypeError):
            return self.async_abort(reason="cannot_connect")
        self._api = api
        self._cohorts = {c["id"]: c["name"] for c in cohorts}

        if user_input is not None:
            self._cohort_id = user_input[CONF_COHORT_ID]
            self._cohort_name = self._cohorts.get(self._cohort_id, "Filc")
            self._interval = user_input[CONF_SCAN_INTERVAL]
            return await self.async_step_groups()

        options = [
            selector.SelectOptionDict(value=c["id"], label=c["name"])
            for c in cohorts
        ]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_COHORT_ID,
                    default=data.get(CONF_COHORT_ID),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60,
                        max=3600,
                        step=30,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_groups(self, user_input=None):
        if self._api is None or self._cohort_id is None:
            return self.async_abort(reason="cannot_connect")
        try:
            groups = await self._api.groups(self._cohort_id)
        except FilcApiError:
            return self.async_abort(reason="cannot_connect")

        divisions = _divisions(groups)
        current = set(self.config_entry.options.get(CONF_SELECTED_GROUP_IDS, []))
        if not divisions:
            return self._save([])
        if user_input is not None:
            return self._save(_picked_groups(divisions, user_input))
        return self.async_show_form(
            step_id="groups", data_schema=_group_schema(divisions, current)
        )

    def _save(self, selected_group_ids: list[str]):
        return self.async_create_entry(
            title="",
            data={
                CONF_COHORT_ID: self._cohort_id,
                CONF_COHORT_NAME: self._cohort_name,
                CONF_TIMETABLE_ID: (self._timetable or {}).get("id"),
                CONF_SELECTED_GROUP_IDS: selected_group_ids,
                CONF_SCAN_INTERVAL: self._interval,
            },
        )
