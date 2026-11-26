"""Exercise filename creation and the Supervisor boundary without a live HA."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path, PurePath
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

ROOT = Path(__file__).parents[1] / "custom_components" / "advanced_backup_manager"


def load_runner():
    """Replace only HA services; CI uses the real pinned Supervisor SDK."""
    modules = {}
    package = types.ModuleType("release_test_abm")
    package.__path__ = [str(ROOT)]
    modules[package.__name__] = package
    try:
        from aiohasupervisor.models.backups import FullBackupOptions
        real_sdk = True
    except ImportError:
        real_sdk = False
        for name in ("aiohasupervisor", "aiohasupervisor.exceptions",
                     "aiohasupervisor.models", "aiohasupervisor.models.backups"):
            modules[name] = types.ModuleType(name)

        @dataclass
        class FullBackupOptions:
            name: str = ""
            password: str = ""
            location: str = ".local"
            background: bool = False
            filename: PurePath | None = None
            homeassistant_exclude_database: bool = False

        @dataclass
        class PartialBackupOptions(FullBackupOptions):
            addons: set | None = None
            homeassistant: bool = True

        @dataclass
        class RemoveBackupOptions:
            location: set | None = None

        sdk = modules["aiohasupervisor.models.backups"]
        sdk.FullBackupOptions = FullBackupOptions
        sdk.PartialBackupOptions = PartialBackupOptions
        sdk.RemoveBackupOptions = RemoveBackupOptions
        modules["aiohasupervisor.exceptions"].SupervisorBadRequestError = RuntimeError

    for name in ("homeassistant", "homeassistant.components",
                 "homeassistant.components.backup", "homeassistant.components.hassio",
                 "homeassistant.components.hassio.handler", "homeassistant.core",
                 "homeassistant.exceptions", "homeassistant.helpers",
                 "homeassistant.helpers.event", "homeassistant.helpers.storage",
                 "homeassistant.util", "homeassistant.util.dt"):
        modules[name] = types.ModuleType(name)
    modules["homeassistant.components"].persistent_notification = types.SimpleNamespace(
        async_create=Mock()
    )
    modules["homeassistant.components.backup"].async_get_manager = Mock()
    modules["homeassistant.components.hassio.handler"].get_supervisor_client = Mock()
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.core"].callback = lambda func: func
    modules["homeassistant.exceptions"].HomeAssistantError = RuntimeError
    modules["homeassistant.helpers.event"].async_track_time_change = Mock()
    modules["homeassistant.helpers.storage"].Store = Mock()
    modules["homeassistant.util.dt"].now = Mock()
    modules["homeassistant.util.dt"].as_local = lambda value: value
    modules["homeassistant.util.dt"].utcnow = lambda: datetime.now(timezone.utc)
    modules["homeassistant.util"].dt = modules["homeassistant.util.dt"]
    loaded = {}
    with patch.dict(sys.modules, modules):
        for name in ("const", "filenames", "messages", "schedule", "runner"):
            spec = importlib.util.spec_from_file_location(
                f"release_test_abm.{name}", ROOT / f"{name}.py"
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            loaded[name] = mod
    return loaded, real_sdk


MODULES, REAL_SDK = load_runner()
runner_module = MODULES["runner"]
backup_filename = MODULES["filenames"].backup_filename


class FilenameTests(unittest.TestCase):
    def test_local_time_and_portable_profile(self):
        stamp = datetime.fromisoformat("2026-11-26T12:02:00+01:00")
        name = backup_filename('Küche / Test:<>?*"\\', stamp)
        self.assertEqual(str(name), "HA_Kuche_Test_2026-11-26_12-02.tar")
        self.assertEqual(len(name.parts), 1)

    def test_empty_reserved_and_long_profile_names(self):
        now = datetime(2026, 11, 26, 12)
        for profile in ("../..", "CON", "", "X" * 1000, "☀"):
            name = str(backup_filename(profile, now))
            self.assertTrue(name.startswith("HA_"))
            self.assertNotIn("..", name)
            self.assertLess(len(name), 160)

    def test_same_minute_and_sanitized_profiles_remain_distinct(self):
        now = datetime(2026, 11, 26, 12)
        first = backup_filename("Full/Test", now)
        second = backup_filename("Full:Test", now, 2)
        self.assertNotEqual(first, second)
        self.assertEqual(str(second), "HA_Full_Test_2026-11-26_12-00_02.tar")

    def test_sequence_is_unbounded_and_validated(self):
        now = datetime(2026, 11, 26, 12)
        self.assertTrue(str(backup_filename("Test", now, 100)).endswith("_100.tar"))
        for invalid in (0, -1, True, "2"):
            with self.assertRaises(ValueError):
                backup_filename("Test", now, invalid)


class NotificationTests(unittest.TestCase):
    def test_german_success_text_for_both_backup_types(self):
        stamp = datetime(2026, 11, 26, 13, 17)
        for kind, label in (("full", "Vollbackup"), ("partial", "Teilbackup")):
            title, message = MODULES["messages"].success_notification(
                "Full Test", kind, stamp, "de-DE"
            )
            self.assertEqual(title, "Backup erfolgreich: Full Test")
            self.assertEqual(message, f"{label} vom 26.11.2026 um 13:17 Uhr wurde erstellt.")

    def test_english_fallback(self):
        title, message = MODULES["messages"].success_notification(
            "Daily", "partial", datetime(2026, 11, 26, 13, 20), "en"
        )
        self.assertEqual(title, "Backup successful: Daily")
        self.assertEqual(message, "Partial backup created on 2026-11-26 at 13:20.")


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runner = runner_module.BackupRunner.__new__(runner_module.BackupRunner)
        self.runner.client = types.SimpleNamespace(
            addons=types.SimpleNamespace(list=AsyncMock(return_value=[
                types.SimpleNamespace(slug="core_mariadb"),
                types.SimpleNamespace(slug="core_mosquitto"),
            ])),
            backups=types.SimpleNamespace(
                full_backup=AsyncMock(), partial_backup=AsyncMock(),
                list=AsyncMock(), backup_info=AsyncMock(), remove_backup=AsyncMock(),
            ),
        )
        self.runner._encryption_key = Mock(return_value="test-only-key")
        self.runner._save = AsyncMock()
        self.runner._notify = Mock()
        self.runner._send_notification = Mock()
        self.runner.hass = types.SimpleNamespace(bus=types.SimpleNamespace(async_fire=Mock()))
        self.runner.lock = asyncio.Lock()
        self.runner.entries = {}
        self.runner.state = {"profiles": {}, "intent": None}
        runner_module.dt_util.now.return_value = datetime.fromisoformat(
            "2026-11-26T12:02:00+01:00"
        )

    def profile(self, kind="full", location=".local"):
        return {"profile_name": "Full Test", "backup_type": kind,
                "location": location, "addons": ["core_mariadb"],
                "addon_mode": "exclude", "include_homeassistant": True,
                "exclude_database": True, "retention": 2}

    async def test_both_backup_types_and_storage_locations(self):
        for kind in ("full", "partial"):
            for location in (".local", "network_test"):
                with self.subTest(kind=kind, location=location):
                    options = await self.runner._async_build_options(self.profile(kind, location))
                    self.assertEqual(options.location, location)
                    self.assertIsInstance(options.filename, PurePath)
                    self.assertTrue(str(options.filename).startswith("HA_Full_Test_2026-11-26_12-02"))
                    self.assertFalse(options.background)
                    self.assertEqual(options.homeassistant_exclude_database, kind == "partial")
                    if kind == "partial":
                        self.assertEqual(options.addons, {"core_mosquitto"})
                    await self.runner._async_create(options)
                    call = (self.runner.client.backups.full_backup if kind == "full"
                            else self.runner.client.backups.partial_backup)
                    call.assert_awaited_with(options)

    async def test_repeated_runs_never_choose_same_filename(self):
        with patch.object(runner_module, "uuid4", side_effect=[UUID(int=1), UUID(int=2)]):
            first = await self.runner._async_build_options(self.profile())
            second = await self.runner._async_build_options(self.profile())
        self.assertNotEqual(first.filename, second.filename)
        self.assertEqual(str(first.filename), "HA_Full_Test_2026-11-26_12-02.tar")
        self.assertEqual(str(second.filename), "HA_Full_Test_2026-11-26_12-02_02.tar")

    async def test_filename_reservations_survive_restart_and_case_collisions(self):
        now = datetime(2026, 11, 26, 12, 2)
        first = self.runner._reserve_filename("Full/Test", now, ".local")
        self.runner.state = json.loads(json.dumps(self.runner.state))
        second = self.runner._reserve_filename("full:test", now, ".local")
        third = self.runner._reserve_filename("Full Test", now, ".local")
        self.assertEqual(str(first), "HA_Full_Test_2026-11-26_12-02.tar")
        self.assertTrue(str(second).endswith("_02.tar"))
        self.assertTrue(str(third).endswith("_03.tar"))
        other_location = self.runner._reserve_filename("Full Test", now, "network_test")
        self.assertEqual(str(other_location), str(first))
        other_minute = self.runner._reserve_filename("Full Test", now.replace(minute=3), ".local")
        self.assertEqual(str(other_minute), "HA_Full_Test_2026-11-26_12-03.tar")

    async def test_load_migrates_old_state_without_changing_intent(self):
        intent = {"entry_id": "entry", "name": "legacy", "location": ".local"}
        self.runner.store = types.SimpleNamespace(async_load=AsyncMock(
            return_value={"profiles": {}, "intent": intent}
        ))
        await self.runner.async_load()
        self.assertEqual(self.runner.state["filename_counters"], {})
        self.assertEqual(self.runner.state["intent"], intent)

    def test_success_notification_uses_local_creation_time_and_has_no_id(self):
        self.runner.hass.config = types.SimpleNamespace(language="de")
        created_at = datetime.fromisoformat("2026-11-26T12:17:00+00:00")
        local_time = datetime.fromisoformat("2026-11-26T13:17:00+01:00")
        notification = runner_module.persistent_notification.async_create
        notification.reset_mock()
        with patch.object(runner_module.dt_util, "as_local", return_value=local_time) as convert:
            self.runner._send_success_notification(
                self.profile() | {"notify_success": True}, "Full Test", created_at
            )
        convert.assert_called_once_with(created_at)
        notification.assert_called_once_with(
            self.runner.hass,
            "Vollbackup vom 26.11.2026 um 13:17 Uhr wurde erstellt.",
            title="Backup erfolgreich: Full Test",
        )
        notification.reset_mock()
        self.runner._send_success_notification(self.profile(), "Full Test", created_at)
        notification.assert_not_called()

    async def test_missing_key_fails_before_creation(self):
        self.runner._encryption_key.return_value = None
        with self.assertRaisesRegex(RuntimeError, "encryption key"):
            await self.runner._async_build_options(self.profile())
        self.runner.client.backups.full_backup.assert_not_awaited()

    async def test_intent_persists_filename_before_supervisor_call(self):
        profile = self.profile()
        self.runner.entries["entry"] = types.SimpleNamespace(
            data=profile, options={}, title="Full Test"
        )
        self.runner.state["profiles"]["entry"] = {"records": []}
        self.runner._async_apply_retention = AsyncMock()

        async def create(options):
            self.assertEqual(self.runner.state["intent"]["filename"], str(options.filename))
            self.assertEqual(list(self.runner.state["filename_counters"].values()), [1])
            self.runner._save.assert_awaited()
            return types.SimpleNamespace(slug="new")

        self.runner.client.backups.full_backup.side_effect = create
        self.runner.client.backups.backup_info.return_value = types.SimpleNamespace(
            slug="new", date=datetime.now(timezone.utc), type="full",
            location_attributes={".local": object()},
        )
        self.assertEqual(await self.runner.async_run("entry", manual=True), "new")
        self.assertIsNone(self.runner.state["intent"])
        self.runner._async_apply_retention.assert_awaited_once_with("entry", 2)

    async def test_failed_intent_save_never_starts_a_backup(self):
        self.runner.entries["entry"] = types.SimpleNamespace(
            data=self.profile(), options={}, title="Full Test"
        )
        self.runner.state["profiles"]["entry"] = {"records": []}
        self.runner._save.side_effect = OSError("Test storage unavailable")
        with self.assertRaises(OSError):
            await self.runner.async_run("entry", manual=True)
        self.runner.client.backups.full_backup.assert_not_awaited()

    async def test_old_intent_reconciles_by_name_and_location(self):
        self.runner.state = {"profiles": {"entry": {"records": []}}, "intent": {
            "entry_id": "entry", "name": "old unique name", "location": "network_test",
        }}
        details = types.SimpleNamespace(
            slug="old", name="old unique name", date=datetime.now(timezone.utc),
            type="full", location_attributes={"network_test": object()},
        )
        self.runner.client.backups.list.return_value = [details]
        self.runner.client.backups.backup_info.return_value = details
        self.assertTrue(await self.runner._async_reconcile())
        self.assertEqual(self.runner.state["profiles"]["entry"]["records"][0]["slug"], "old")

    async def test_retention_uses_recorded_slug_and_location(self):
        self.runner.state["profiles"]["entry"] = {"records": [
            {"slug": "old", "created_at": "2026-11-25", "location": "network_test"},
            {"slug": "new", "created_at": "2026-11-26", "location": ".local"},
        ]}
        await self.runner._async_apply_retention("entry", 1)
        call = self.runner.client.backups.remove_backup.await_args
        self.assertEqual(call.args, ("old",))
        self.assertEqual(call.kwargs["options"].location, {"network_test"})
        self.assertEqual(len(self.runner.state["profiles"]["entry"]["records"]), 1)

    @unittest.skipUnless(REAL_SDK, "Real SDK serialization is checked by Python 3.13 CI")
    async def test_sdk_serializes_filename_for_both_backup_types(self):
        for kind in ("full", "partial"):
            options = await self.runner._async_build_options(self.profile(kind))
            payload = options.to_dict()
            self.assertEqual(payload["filename"], str(options.filename))
            self.assertEqual(payload["location"], ".local")


if __name__ == "__main__":
    unittest.main()
