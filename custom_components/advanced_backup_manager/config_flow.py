""""Config and options flow for independent backup profiles."""
from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from aiohasupervisor.models.mounts import MountState, MountUsage
from homeassistant import config_entries
from homeassistant.components.hassio.handler import get_supervisor_client
from homeassistant.helpers import selector
from homeassistant.exceptions import HomeAssistantError

from .const import *
from .models import validate_profile

_WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _start_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the short first step that determines the dynamic fields."""
    d = lambda key, fallback=None: defaults.get(key, fallback)
    return vol.Schema(
        {
            vol.Required(
                CONF_PROFILE_NAME, default=d(CONF_PROFILE_NAME, "")
            ): selector.TextSelector(),
            vol.Required(
                CONF_BACKUP_TYPE, default=d(CONF_BACKUP_TYPE, BACKUP_PARTIAL)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[BACKUP_PARTIAL, BACKUP_FULL],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_SCHEDULE, default=d(CONF_SCHEDULE, SCHEDULE_DAILY)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[SCHEDULE_DAILY, SCHEDULE_WEEKDAYS, SCHEDULE_INTERVAL],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _details_schema(
    defaults: dict[str, Any],
    addons: list[tuple[str, str]],
    locations: list[tuple[str, str]],
) -> vol.Schema:
    """Build only the fields relevant to the selected schedule."""
    d = lambda key, fallback=None: defaults.get(key, fallback)
    is_full_backup = d(CONF_BACKUP_TYPE) == BACKUP_FULL
    schema: dict[Any, Any] = {
        vol.Required(CONF_TIME, default=d(CONF_TIME, "03:00")): selector.TimeSelector(),
    }

    if d(CONF_SCHEDULE) == SCHEDULE_WEEKDAYS:
        weekday_values = d(CONF_WEEKDAYS, [0])
        if isinstance(weekday_values, (int, str)):
            weekday_values = [weekday_values]
        schema[vol.Required(CONF_WEEKDAYS, default=[str(value) for value in weekday_values])] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": str(index), "label": name}
                        for index, name in enumerate(_WEEKDAY_NAMES)
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            )
        )
    elif d(CONF_SCHEDULE) == SCHEDULE_INTERVAL:
        schema[vol.Required(CONF_INTERVAL_DAYS, default=d(CONF_INTERVAL_DAYS, 3))] = (
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=366, step=1, mode=selector.NumberSelectorMode.BOX
                )
            )
        )
        schema[vol.Required(
            CONF_ANCHOR_DATE, default=d(CONF_ANCHOR_DATE, date.today().isoformat())
        )] = selector.DateSelector()

    schema.update(
        {
            vol.Required(
                CONF_RETENTION, default=d(CONF_RETENTION, 3)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=365, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_LOCATION, default=d(CONF_LOCATION, ".local")): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": value, "label": label}
                            for value, label in locations
                        ]
                    )
                )
            ),
            vol.Required(
                CONF_ADDON_MODE, default=d(CONF_ADDON_MODE, ADDON_EXCLUDE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[ADDON_INCLUDE, ADDON_EXCLUDE])
            ),
            vol.Optional(CONF_ADDONS, default=d(CONF_ADDONS, [])): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": slug, "label": name} for slug, name in addons
                        ],
                        multiple=True,
                    )
                )
            ),
            vol.Required(
                CONF_INCLUDE_HOMEASSISTANT,
                default=d(CONF_INCLUDE_HOMEASSISTANT, True),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EXCLUDE_DATABASE, default=d(CONF_EXCLUDE_DATABASE, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_SUCCESS, default=d(CONF_NOTIFY_SUCCESS, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_FAILURE, default=d(CONF_NOTIFY_FAILURE, True)
            ): selector.BooleanSelector(),
        }
    )
    if is_full_backup:
        partial_only = {
            CONF_ADDON_MODE,
            CONF_ADDONS,
            CONF_INCLUDE_HOMEASSISTANT,
            CONF_EXCLUDE_DATABASE,
        }
        schema = {
            key: value
            for key, value in schema.items()
            if getattr(key, "schema", None) not in partial_only
        }
    return vol.Schema(schema)


async def _locations(hass) -> list[tuple[str, str]]:
    try:
        mounts = await get_supervisor_client(hass).mounts.info()
        return [(".local", "Home Assistant local")] + [
            (mount.name, mount.name)
            for mount in mounts.mounts
            if mount.usage is MountUsage.BACKUP and mount.state is MountState.ACTIVE
        ]
    except Exception:
        return [(".local", "Home Assistant local")]


async def _addons(hass) -> list[tuple[str, str]]:
    try:
        return sorted(
            (addon.slug, addon.name)
            for addon in await get_supervisor_client(hass).addons.list()
        )
    except Exception:
        # The form remains usable; submission will still require a working Supervisor.
        return []


class AdvancedBackupManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a new independent backup profile."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Choose the profile basics and schedule first."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=_start_schema({})
            )
        self._profile_data = user_input
        return await self.async_step_details()

    async def async_step_details(self, user_input: dict[str, Any] | None = None):
        """Show only fields relevant to the selected schedule."""
        addons = await _addons(self.hass)
        locations = await _locations(self.hass)
        if user_input is not None:
            data = self._profile_data | user_input
            try:
                data = validate_profile(data)
            except (ValueError, HomeAssistantError) as err:
                return self.async_show_form(
                    step_id="details",
                    data_schema=_details_schema(
                        data, addons, locations
                    ),
                    errors={"base": str(err)},
                )
            return self.async_create_entry(title=data[CONF_PROFILE_NAME], data=data)

        return self.async_show_form(
            step_id="details",
            data_schema=_details_schema(
                self._profile_data, addons, locations
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the profile options flow."""
        return AdvancedBackupManagerOptionsFlow()


class AdvancedBackupManagerOptionsFlow(config_entries.OptionsFlow):
    """Edit a backup profile through the same guided flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Edit this backup plan."""
        return await self.async_step_profile(user_input)

    async def async_step_profile(self, user_input: dict[str, Any] | None = None):
        """Choose the profile basics and schedule first."""
        defaults = dict(self.config_entry.data) | dict(self.config_entry.options)
        if user_input is None:
            return self.async_show_form(
                step_id="init", data_schema=_start_schema(defaults)
            )
        self._original_data = defaults
        self._profile_data = defaults | user_input
        return await self.async_step_details()

    async def async_step_details(self, user_input: dict[str, Any] | None = None):
        """Show only fields relevant to the selected schedule."""
        addons = await _addons(self.hass)
        locations = await _locations(self.hass)
        if user_input is not None:
            data = self._profile_data | user_input
            # Encryption is integration-wide; old profile-specific values are
            # intentionally discarded when a profile is next saved.
            data.pop(CONF_PASSWORD, None)
            try:
                data = validate_profile(data)
            except ValueError as err:
                return self.async_show_form(
                    step_id="details",
                    data_schema=_details_schema(data, addons, locations),
                    errors={"base": str(err)},
                )
            return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="details",
            data_schema=_details_schema(self._profile_data, addons, locations),
        )
