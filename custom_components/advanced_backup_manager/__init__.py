"""Advanced Backup Manager integration."""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
import voluptuous as vol
from .const import *
from .runner import BackupRunner

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up global services exactly once."""
    runner = BackupRunner(hass)
    await runner.async_load()
    hass.data[DOMAIN] = {DATA_RUNNER: runner}
    async def run(call):
        await runner.async_run(call.data[ATTR_ENTRY_ID], manual=True)
    async def resolve(call):
        await runner.async_resolve_uncertain(call.data[ATTR_ENTRY_ID], call.data["outcome"])
    hass.services.async_register(DOMAIN, SERVICE_RUN, run, schema=vol.Schema({vol.Required(ATTR_ENTRY_ID): cv.string}))
    hass.services.async_register(DOMAIN, SERVICE_RESOLVE_UNCERTAIN, resolve, schema=vol.Schema({vol.Required(ATTR_ENTRY_ID): cv.string, vol.Required("outcome"): vol.In(["no_backup_created", "backup_exists"]) }))
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one independent profile."""
    runner: BackupRunner = hass.data[DOMAIN][DATA_RUNNER]
    await runner.async_add_entry(entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await hass.data[DOMAIN][DATA_RUNNER].async_remove_entry(entry.entry_id)
    return unloaded
