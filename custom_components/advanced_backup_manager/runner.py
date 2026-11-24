""""Serialized and conservative Supervisor backup execution."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from aiohasupervisor.models.backups import (
    AddonSet,
    FullBackupOptions,
    PartialBackupOptions,
    RemoveBackupOptions,
)
from homeassistant.components import persistent_notification
from homeassistant.components.backup import async_get_manager
from homeassistant.components.hassio.handler import get_supervisor_client
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import *
from .schedule import is_due

_LOGGER = logging.getLogger(__name__)


class BackupRunner:
    """One runner, one global lock, persisted intent before every API call."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.client = get_supervisor_client(hass)
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.state: dict[str, Any] = {"profiles": {}, "intent": None}
        self.entries: dict[str, Any] = {}
        self.lock = asyncio.Lock()
        self._unsub = None
        self.listeners: list[callback] = []

    async def async_load(self) -> None:
        self.state = await self.store.async_load() or {"profiles": {}, "intent": None}
        self.state.setdefault("profiles", {})
        self.state.setdefault("intent", None)

    async def async_add_entry(self, entry: Any) -> None:
        self.entries[entry.entry_id] = entry
        is_new_profile = entry.entry_id not in self.state["profiles"]
        profile = self.state["profiles"].setdefault(
            entry.entry_id,
            {"records": [], "last_scheduled_date": None, "last_result": None},
        )
        await self._save()
        if self._unsub is None:
            self._unsub = async_track_time_change(
                self.hass, self._async_time_tick, second=0
            )
        if is_new_profile:
            # A single, explicit test run confirms the selected location and
            # credentials. Mark today as handled to avoid a second scheduled run.
            profile["last_scheduled_date"] = dt_util.now().date().isoformat()
            await self._save()
            persistent_notification.async_create(
                self.hass,
                "A one-time test backup is starting to verify this profile and "
                "its selected storage location.",
                title=f"Advanced Backup: {entry.title}",
            )
            self.hass.async_create_task(self.async_run(entry.entry_id, manual=True))

    async def async_remove_entry(self, entry_id: str) -> None:
        self.entries.pop(entry_id, None)
        if not self.entries and self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def add_listener(self, listener) -> callback:
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def profile_state(self, entry_id: str) -> dict[str, Any]:
        return self.state["profiles"].get(entry_id, {})

    async def _save(self) -> None:
        await self.store.async_save(self.state)

    async def _async_time_tick(self, now: datetime) -> None:
        for entry_id, entry in tuple(self.entries.items()):
            state = self.profile_state(entry_id)
            if is_due(
                self._profile_data(entry), now, state.get("last_scheduled_date")
            ):
                # A busy runner deliberately drops a scheduled trigger, rather than queueing it.
                if not self.lock.locked():
                    self.hass.async_create_task(
                        self.async_run(
                            entry_id,
                            manual=False,
                            scheduled_date=now.date().isoformat(),
                        )
                    )

    async def async_run(
        self, entry_id: str, *, manual: bool, scheduled_date: str | None = None
    ) -> str:
        """Make and verify a backup. An API error leaves the intent as uncertain."""
        if self.lock.locked():
            raise HomeAssistantError(
                "Another Advanced Backup Manager backup is running; no queue is used"
            )
        if self.state.get("intent"):
            raise HomeAssistantError(
                "An earlier backup has an uncertain result; resolve it first"
            )
        entry = self.entries.get(entry_id)
        if entry is None:
            raise HomeAssistantError("Unknown backup profile")

        async with self.lock:
            profile = self.profile_state(entry_id)
            profile_data = self._profile_data(entry)
            backup_options = await self._async_build_options(profile_data)
            self.state["intent"] = {
                "entry_id": entry_id,
                "started_at": dt_util.utcnow().isoformat(),
                "scheduled_date": scheduled_date,
            }
            await self._save()
            try:
                backup = await self._async_create(backup_options)
                if not backup.slug:
                    raise HomeAssistantError(
                        "Supervisor returned no completed backup ID"
                    )
                details = await self.client.backups.backup_info(backup.slug)
                if profile_data[CONF_LOCATION] not in details.location_attributes:
                    raise HomeAssistantError(
                        "Supervisor did not create the backup in the configured "
                        f"location: {profile_data[CONF_LOCATION]}"
                    )
                record = {
                    "slug": details.slug,
                    "created_at": details.date.isoformat(),
                    "type": str(details.type),
                    "location": profile_data[CONF_LOCATION],
                }
                profile["records"].append(record)
                profile["last_result"] = {
                    "status": "success",
                    "backup_id": details.slug,
                    "at": dt_util.utcnow().isoformat(),
                }
                if scheduled_date:
                    profile["last_scheduled_date"] = scheduled_date
                self.state["intent"] = None
                await self._save()
            except Exception as err:
                # Intent stays durable: request may have reached Supervisor even when response failed.
                profile["last_result"] = {
                    "status": "uncertain",
                    "error": str(err),
                    "at": dt_util.utcnow().isoformat(),
                }
                await self._save()
                self.hass.bus.async_fire(
                    EVENT_BACKUP_FAILED,
                    {
                        ATTR_ENTRY_ID: entry_id,
                        ATTR_PROFILE_NAME: entry.title,
                        "error": str(err),
                        "uncertain": True,
                    },
                )
                self._send_notification(
                    profile_data,
                    entry.title,
                    f"Backup needs review: {err}",
                    success=False,
                )
                self._notify()
                raise

            # Everything below is post-processing. It must never turn a verified
            # Supervisor backup into an uncertain run.
            await self._async_apply_retention(entry_id, profile_data[CONF_RETENTION])
            self.hass.bus.async_fire(
                EVENT_BACKUP_COMPLETED,
                {
                    ATTR_ENTRY_ID: entry_id,
                    ATTR_PROFILE_NAME: entry.title,
                    ATTR_BACKUP_ID: details.slug,
                    "manual": manual,
                },
            )
            self._send_notification(
                profile_data,
                entry.title,
                f"Backup {details.slug} completed",
                success=True,
            )
            self._notify()
            return details.slug

    async def _async_build_options(
        self, data: dict[str, Any]
    ) -> FullBackupOptions | PartialBackupOptions:
        """Build validated options without making a side-effecting API call."""
        name = (
            f"ABM {data[CONF_PROFILE_NAME]} "
            f"{dt_util.now().strftime('%Y-%m-%d %H:%M')}"
        )
        common = {
            "name": name,
            "location": data[CONF_LOCATION],
            "background": False,
        }
        # Use Home Assistant's central backup encryption key. It is managed
        # exclusively by the native Backup integration and its emergency kit.
        password = async_get_manager(self.hass).config.data.create_backup.password
        if password:
            common["password"] = password
        if data[CONF_BACKUP_TYPE] == BACKUP_FULL:
            return FullBackupOptions(
                **common, homeassistant_exclude_database=False
            )

        installed = {addon.slug for addon in await self.client.addons.list()}
        chosen = set(data[CONF_ADDONS])
        addons = (
            chosen
            if data[CONF_ADDON_MODE] == ADDON_INCLUDE
            else installed - chosen
        )
        if not addons and not data[CONF_INCLUDE_HOMEASSISTANT]:
            raise HomeAssistantError(
                "Partial backup has neither Home Assistant nor an installed add-on to include"
            )
        return PartialBackupOptions(
            **common,
            addons=addons or None,
            homeassistant=data[CONF_INCLUDE_HOMEASSISTANT],
            homeassistant_exclude_database=data[CONF_EXCLUDE_DATABASE],
        )

    async def _async_create(
        self, options: FullBackupOptions | PartialBackupOptions
    ):
        """Start the backup only after its durable intent has been saved."""
        if isinstance(options, PartialBackupOptions):
            return await self.client.backups.partial_backup(options)
        return await self.client.backups.full_backup(options)

    @staticmethod
    def _profile_data(entry: Any) -> dict[str, Any]:
        """Options override entry data after native options-flow edits."""
        return dict(entry.data) | dict(entry.options)

    async def _async_apply_retention(self, entry_id: str, retention: int) -> None:
        records = self.profile_state(entry_id)["records"]
        records.sort(key=lambda item: item["created_at"], reverse=True)
        for record in records[max(1, retention):]:
            try:
                await self.client.backups.backup_info(record["slug"])
                await self.client.backups.remove_backup(
                    record["slug"],
                    options=RemoveBackupOptions(
                        location={record.get("location", ".local")}
                    ),
                )
            except Exception as err:
                _LOGGER.warning(
                    "Retention left backup %s untouched: %s", record["slug"], err
                )
                continue
            records.remove(record)
            await self._save()

    async def async_resolve_uncertain(self, entry_id: str, outcome: str) -> None:
        intent = self.state.get("intent")
        if not intent or intent["entry_id"] != entry_id:
            raise HomeAssistantError("No uncertain execution exists for this profile")
        self.state["intent"] = None
        self.profile_state(entry_id)["last_result"] = {
            "status": "resolved",
            "outcome": outcome,
            "at": dt_util.utcnow().isoformat(),
        }
        await self._save()
        self._notify()

    def _send_notification(
        self, data: dict[str, Any], title: str, message: str, *, success: bool
    ) -> None:
        """Create an optional local notification without exposing secrets."""
        if data.get(CONF_NOTIFY_SUCCESS if success else CONF_NOTIFY_FAILURE):
            persistent_notification.async_create(
                self.hass, message, title=f"Advanced Backup: {title}"
            )

    def _notify(self) -> None:
        """Refresh listeners without allowing UI failures to affect backups."""
        for listener in tuple(self.listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Could not update an Advanced Backup Manager entity")
