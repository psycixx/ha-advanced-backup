""""Status and profile summary sensor per backup profile."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import device_info
from .const import (
    CONF_ADDON_MODE,
    CONF_ADDONS,
    CONF_ANCHOR_DATE,
    CONF_BACKUP_TYPE,
    CONF_EXCLUDE_DATABASE,
    CONF_INCLUDE_HOMEASSISTANT,
    CONF_INTERVAL_DAYS,
    CONF_LOCATION,
    CONF_NOTIFY_FAILURE,
    CONF_NOTIFY_SUCCESS,
    CONF_RETENTION,
    CONF_SCHEDULE,
    CONF_TIME,
    CONF_WEEKDAYS,
    DOMAIN,
    SCHEDULE_DAILY,
    SCHEDULE_WEEKDAYS,
)


async def async_setup_entry(hass, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Add one status sensor for the backup profile."""
    async_add_entities([ProfileStatusSensor(hass, entry), PlanConfigurationSensor(hass, entry)])


class ProfileStatusSensor(SensorEntity):
    """Expose the result and non-sensitive configuration of one profile."""

    _attr_has_entity_name = True
    _attr_name = "Backup status"
    _attr_icon = "mdi:backup-restore"

    def __init__(self, hass, entry) -> None:
        self._entry = entry
        self._attr_name = f"{entry.title} backup status"
        self._runner = hass.data[DOMAIN]["runner"]
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = device_info(entry)
        self._unsub = self._runner.add_listener(self._handle_runner_update)

    @callback
    def _handle_runner_update(self) -> None:
        """Write state only after Home Assistant has registered the entity."""
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the most recent execution state."""
        return self._runner.profile_state(self._entry.entry_id).get(
            "last_result", {}
        ).get("status", "idle")

    @property
    def extra_state_attributes(self):
        """Expose the profile configuration without its password."""
        state = self._runner.profile_state(self._entry.entry_id)
        profile = dict(self._entry.data) | dict(self._entry.options)
        return {
            "backup_type": profile.get(CONF_BACKUP_TYPE),
            "schedule": profile.get(CONF_SCHEDULE),
            "time": profile.get(CONF_TIME),
            "weekday": (profile.get(CONF_WEEKDAYS) or [None])[0],
            "interval_days": profile.get(CONF_INTERVAL_DAYS),
            "anchor_date": profile.get(CONF_ANCHOR_DATE),
            "location": profile.get(CONF_LOCATION),
            "retention": profile.get(CONF_RETENTION),
            "addon_mode": profile.get(CONF_ADDON_MODE),
            "addons": profile.get(CONF_ADDONS, []),
            "include_homeassistant": profile.get(CONF_INCLUDE_HOMEASSISTANT),
            "exclude_database": profile.get(CONF_EXCLUDE_DATABASE),
            "notify_success": profile.get(CONF_NOTIFY_SUCCESS),
            "notify_failure": profile.get(CONF_NOTIFY_FAILURE),
            "last_result": state.get("last_result"),
            "managed_backups": len(state.get("records", [])),
            "blocked": bool(self._runner.state.get("intent")),
        }

    async def async_will_remove_from_hass(self):
        """Unsubscribe from runner state changes."""
        self._unsub()


class PlanConfigurationSensor(SensorEntity):
    """Expose one backup plan's readable schedule and key settings."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, hass, entry) -> None:
        """Initialize the plan configuration entity."""
        self._entry = entry
        self._runner = hass.data[DOMAIN]["runner"]
        self._attr_name = f"{entry.title} configuration"
        self._attr_unique_id = f"{entry.entry_id}_configuration"
        self._attr_device_info = device_info(entry)
        self._unsub = self._runner.add_listener(self._handle_runner_update)

    @callback
    def _handle_runner_update(self) -> None:
        """Refresh when configuration-related state changes."""
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        """Return a readable schedule summary."""
        profile = dict(self._entry.data) | dict(self._entry.options)
        schedule = profile.get(CONF_SCHEDULE)
        run_time = profile.get(CONF_TIME)
        if schedule == SCHEDULE_DAILY:
            return f"daily at {run_time}"
        if schedule == SCHEDULE_WEEKDAYS:
            weekday = (profile.get(CONF_WEEKDAYS) or [None])[0]
            return f"weekly on weekday {weekday} at {run_time}"
        return f"every {profile.get(CONF_INTERVAL_DAYS)} days at {run_time}"

    @property
    def extra_state_attributes(self):
        """Return safe plan settings for dashboards and automations."""
        profile = dict(self._entry.data) | dict(self._entry.options)
        return {
            "backup_type": profile.get(CONF_BACKUP_TYPE),
            "location": profile.get(CONF_LOCATION),
            "retention": profile.get(CONF_RETENTION),
            "schedule": profile.get(CONF_SCHEDULE),
            "time": profile.get(CONF_TIME),
            "weekday": (profile.get(CONF_WEEKDAYS) or [None])[0],
            "interval_days": profile.get(CONF_INTERVAL_DAYS),
            "anchor_date": profile.get(CONF_ANCHOR_DATE),
            "notifications_enabled": {
                "success": profile.get(CONF_NOTIFY_SUCCESS),
                "failure": profile.get(CONF_NOTIFY_FAILURE),
            },
        }

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from runner updates."""
        self._unsub()
