"""Config and options flow for independent backup profiles."""
from __future__ import annotations
from datetime import date
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.hassio.handler import get_supervisor_client
from homeassistant.helpers import selector
from aiohasupervisor.models.mounts import MountState, MountUsage
from .const import *
from .models import validate_profile

_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

def _schema(defaults: dict[str, Any], addons: list[tuple[str, str]], locations: list[tuple[str, str]]) -> vol.Schema:
    """Build one native HA form; all schedule-specific values are retained."""
    d = lambda key, fallback=None: defaults.get(key, fallback)
    weekday_defaults = [str(day) for day in d(CONF_WEEKDAYS, [])]
    return vol.Schema({
        vol.Required(CONF_PROFILE_NAME, default=d(CONF_PROFILE_NAME, "")): selector.TextSelector(),
        vol.Required(CONF_BACKUP_TYPE, default=d(CONF_BACKUP_TYPE, BACKUP_PARTIAL)): selector.SelectSelector(selector.SelectSelectorConfig(options=[BACKUP_PARTIAL, BACKUP_FULL], mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_SCHEDULE, default=d(CONF_SCHEDULE, SCHEDULE_DAILY)): selector.SelectSelector(selector.SelectSelectorConfig(options=[SCHEDULE_DAILY, SCHEDULE_WEEKDAYS, SCHEDULE_INTERVAL])),
        vol.Required(CONF_TIME, default=d(CONF_TIME, "03:00")): selector.TimeSelector(),
        # SelectSelector option values must be strings. Values are converted back
        # to weekday numbers by validate_profile before storing the profile.
        vol.Optional(CONF_WEEKDAYS, default=weekday_defaults): selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value": str(i), "label": name} for i, name in enumerate(_WEEKDAY_NAMES)], multiple=True)),
        vol.Optional(CONF_INTERVAL_DAYS, default=d(CONF_INTERVAL_DAYS, 3)): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=366, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_ANCHOR_DATE, default=d(CONF_ANCHOR_DATE, date.today().isoformat())): selector.DateSelector(),
        vol.Required(CONF_RETENTION, default=d(CONF_RETENTION, 3)): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=365, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Required(CONF_LOCATION, default=d(CONF_LOCATION, ".local")): selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value": value, "label": label} for value, label in locations])),
        vol.Required(CONF_NOTIFY_SUCCESS, default=d(CONF_NOTIFY_SUCCESS, False)): selector.BooleanSelector(),
        vol.Required(CONF_NOTIFY_FAILURE, default=d(CONF_NOTIFY_FAILURE, True)): selector.BooleanSelector(),
        vol.Required(CONF_ADDON_MODE, default=d(CONF_ADDON_MODE, ADDON_EXCLUDE)): selector.SelectSelector(selector.SelectSelectorConfig(options=[ADDON_INCLUDE, ADDON_EXCLUDE])),
        vol.Optional(CONF_ADDONS, default=d(CONF_ADDONS, [])): selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value": slug, "label": name} for slug, name in addons], multiple=True)),
        vol.Required(CONF_INCLUDE_HOMEASSISTANT, default=d(CONF_INCLUDE_HOMEASSISTANT, True)): selector.BooleanSelector(),
        vol.Required(CONF_EXCLUDE_DATABASE, default=d(CONF_EXCLUDE_DATABASE, True)): selector.BooleanSelector(),
        # Do not put the stored password back in a form default. On options
        # edits a blank field means "retain existing password".
        vol.Optional(CONF_PASSWORD, default=""): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    })

async def _locations(hass) -> list[tuple[str, str]]:
    try:
        mounts = await get_supervisor_client(hass).mounts.info()
        return [(".local", "Home Assistant local")] + [(mount.name, mount.name) for mount in mounts.mounts if mount.usage is MountUsage.BACKUP and mount.state is MountState.ACTIVE]
    except Exception:
        return [(".local", "Home Assistant local")]

async def _addons(hass) -> list[tuple[str, str]]:
    try:
        return sorted((addon.slug, addon.name) for addon in await get_supervisor_client(hass).addons.list())
    except Exception:
        # The form remains usable; submission will still require a working Supervisor.
        return []

class AdvancedBackupManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        addons = await _addons(self.hass)
        locations = await _locations(self.hass)
        if user_input is not None:
            if not user_input.get(CONF_PASSWORD):
                user_input.pop(CONF_PASSWORD, None)
            try: data = validate_profile(user_input)
            except ValueError as err: return self.async_show_form(step_id="user", data_schema=_schema(user_input, addons, locations), errors={"base": str(err)})
            return self.async_create_entry(title=data[CONF_PROFILE_NAME], data=data)
        return self.async_show_form(step_id="user", data_schema=_schema({}, addons, locations))
    @staticmethod
    def async_get_options_flow(config_entry): return AdvancedBackupManagerOptionsFlow()

class AdvancedBackupManagerOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        defaults = dict(self.config_entry.data) | dict(self.config_entry.options)
        addons = await _addons(self.hass)
        locations = await _locations(self.hass)
        if user_input is not None:
            if not user_input.get(CONF_PASSWORD):
                user_input[CONF_PASSWORD] = defaults.get(CONF_PASSWORD)
            try: data = validate_profile(user_input)
            except ValueError as err: return self.async_show_form(step_id="init", data_schema=_schema(user_input, addons, locations), errors={"base": str(err)})
            return self.async_create_entry(title="", data=data)
        return self.async_show_form(step_id="init", data_schema=_schema(defaults, addons, locations))
