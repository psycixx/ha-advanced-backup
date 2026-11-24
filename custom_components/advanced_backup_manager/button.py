""""Button entities for manually starting backup profiles."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import device_info


async def async_setup_entry(hass, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Add one manual-run button for the backup profile."""
    async_add_entities([RunBackupButton(hass, entry)])


class RunBackupButton(ButtonEntity):
    """Start a configured profile immediately."""

    _attr_has_entity_name = True
    _attr_name = "Run backup now"
    _attr_icon = "mdi:backup-restore"

    def __init__(self, hass, entry) -> None:
        self._entry = entry
        self._attr_name = f"{entry.title} run backup now"
        self._runner = hass.data[DOMAIN]["runner"]
        self._attr_unique_id = f"{entry.entry_id}_run"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        """Run the profile with the same safety checks as scheduled execution."""
        await self._runner.async_run(self._entry.entry_id, manual=True)

