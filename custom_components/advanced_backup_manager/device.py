"""Device metadata for backup-plan entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def device_info(entry) -> DeviceInfo:
    """Build the shared device entry for one backup plan."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Advanced Backup Manager",
        model="Backup plan",
        configuration_url="https://github.com/psycixx/ha-advanced-backup",
    )
