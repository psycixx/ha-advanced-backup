"""Serialized and conservative Supervisor backup execution."""
from __future__ import annotations
import asyncio
from datetime import datetime
import logging
from typing import Any
from aiohasupervisor.models.backups import AddonSet, FullBackupOptions, PartialBackupOptions
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
        self.state["profiles"].setdefault(entry.entry_id, {"records": [], "last_scheduled_date": None, "last_result": None})
        await self._save()
        if self._unsub is None:
            self._unsub = async_track_time_change(self.hass, self._async_time_tick, second=0)

    async def async_remove_entry(self, entry_id: str) -> None:
        self.entries.pop(entry_id, None)
        if not self.entries and self._unsub:
            self._unsub(); self._unsub = None

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
            if is_due(self._profile_data(entry), now, state.get("last_scheduled_date")):
                # A busy runner deliberately drops a scheduled trigger, rather than queueing it.
                if not self.lock.locked():
                    self.hass.async_create_task(self.async_run(entry_id, manual=False, scheduled_date=now.date().isoformat()))

    async def async_run(self, entry_id: str, *, manual: bool, scheduled_date: str | None = None) -> str:
        """Make and verify a backup. An API error leaves the intent as uncertain."""
        if self.lock.locked():
            raise HomeAssistantError("Another Advanced Backup Manager backup is running; no queue is used")
        if self.state.get("intent"):
            raise HomeAssistantError("An earlier backup has an uncertain result; resolve it first")
        entry = self.entries.get(entry_id)
        if entry is None:
            raise HomeAssistantError("Unknown backup profile")
        async with self.lock:
            profile = self.profile_state(entry_id)
            self.state["intent"] = {"entry_id": entry_id, "started_at": dt_util.utcnow().isoformat(), "scheduled_date": scheduled_date}
            await self._save()  # durable before the potentially side-effecting request
            try:
                profile_data = self._profile_data(entry)
                backup = await self._async_create(profile_data)
                if not backup.slug:
                    raise HomeAssistantError("Supervisor returned no completed backup ID")
                # A returned slug alone is not sufficient evidence; request the completed details.
                details = await self.client.backups.backup_info(backup.slug)
                record = {"slug": details.slug, "created_at": details.date.isoformat(), "type": str(details.type)}
                profile["records"].append(record)
                profile["last_result"] = {"status": "success", "backup_id": details.slug, "at": dt_util.utcnow().isoformat()}
                if scheduled_date:
                    profile["last_scheduled_date"] = scheduled_date
                self.state["intent"] = None
                await self._save()
                await self._async_apply_retention(entry_id, profile_data[CONF_RETENTION])
                self.hass.bus.async_fire(EVENT_BACKUP_COMPLETED, {ATTR_ENTRY_ID: entry_id, ATTR_PROFILE_NAME: entry.title, ATTR_BACKUP_ID: details.slug, "manual": manual})
                self._notify()
                return details.slug
            except Exception as err:
                # Intent stays durable: request may have reached Supervisor even when response failed.
                profile["last_result"] = {"status": "uncertain", "error": str(err), "at": dt_util.utcnow().isoformat()}
                await self._save()
                self.hass.bus.async_fire(EVENT_BACKUP_FAILED, {ATTR_ENTRY_ID: entry_id, ATTR_PROFILE_NAME: entry.title, "error": str(err), "uncertain": True})
                self._notify()
                raise

    async def _async_create(self, data: dict[str, Any]):
        name = f"ABM {data[CONF_PROFILE_NAME]} {dt_util.now().strftime('%Y-%m-%d %H:%M')}"
        common = {"name": name, "location": ".local", "background": False}
        if password := data.get(CONF_PASSWORD):
            common["password"] = password
        if data[CONF_BACKUP_TYPE] == BACKUP_FULL:
            # Be explicit: a profile called "full" must never inherit a future
            # Supervisor default that excludes the database.
            return await self.client.backups.full_backup(FullBackupOptions(**common, homeassistant_exclude_database=False))
        installed = {addon.slug for addon in await self.client.addons.list()}
        chosen = set(data[CONF_ADDONS])
        addons: AddonSet | set[str]
        addons = chosen & installed if data[CONF_ADDON_MODE] == ADDON_INCLUDE else installed - chosen
        # Include HA by default; the model rejects an empty partial selection.
        return await self.client.backups.partial_backup(PartialBackupOptions(**common, addons=addons or None, homeassistant=data[CONF_INCLUDE_HOMEASSISTANT], homeassistant_exclude_database=data[CONF_EXCLUDE_DATABASE]))

    @staticmethod
    def _profile_data(entry: Any) -> dict[str, Any]:
        """Options override entry data after native options-flow edits."""
        return dict(entry.data) | dict(entry.options)

    async def _async_apply_retention(self, entry_id: str, retention: int) -> None:
        records = self.profile_state(entry_id)["records"]
        records.sort(key=lambda item: item["created_at"], reverse=True)
        # Keep at least one own confirmed backup independent of a bad setting.
        for record in records[max(1, retention):]:
            try:
                await self.client.backups.backup_info(record["slug"])
                await self.client.backups.remove_backup(record["slug"])
            except Exception as err:
                _LOGGER.warning("Retention left backup %s untouched: %s", record["slug"], err)
                continue
            records.remove(record)
            await self._save()

    async def async_resolve_uncertain(self, entry_id: str, outcome: str) -> None:
        intent = self.state.get("intent")
        if not intent or intent["entry_id"] != entry_id:
            raise HomeAssistantError("No uncertain execution exists for this profile")
        # Confirmation is deliberately manual after inspecting Supervisor; no guessing or retry.
        self.state["intent"] = None
        self.profile_state(entry_id)["last_result"] = {"status": "resolved", "outcome": outcome, "at": dt_util.utcnow().isoformat()}
        await self._save(); self._notify()

    def _notify(self) -> None:
        for listener in tuple(self.listeners): listener()
