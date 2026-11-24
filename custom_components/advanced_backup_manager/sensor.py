"""Status sensor per backup profile."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([ProfileStatusSensor(hass, entry)])

class ProfileStatusSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Backup status"
    _attr_icon = "mdi:backup-restore"
    def __init__(self, hass, entry) -> None:
        self._entry = entry; self._runner = hass.data[DOMAIN]["runner"]
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._unsub = self._runner.add_listener(self.async_write_ha_state)
    @property
    def native_value(self):
        return self._runner.profile_state(self._entry.entry_id).get("last_result", {}).get("status", "idle")
    @property
    def extra_state_attributes(self):
        state = self._runner.profile_state(self._entry.entry_id)
        return {"last_result": state.get("last_result"), "managed_backups": len(state.get("records", [])), "blocked": bool(self._runner.state.get("intent"))}
    async def async_will_remove_from_hass(self): self._unsub()
