"""Exercise filename creation and the Supervisor boundary without a live HA."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
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
    modules["homeassistant.util.dt"].utcnow = lambda: datetime.now(timezone.utc)
    modules["homeassistant.util"].dt = modules["homeassistant.util.dt"]
    loaded = {}
    with patch.dict(sys.modules, modules):
        for name in ("const", "filenames", "schedule", "runner"):
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
        name = backup_filename('Küche / Test:<>?*"\\', stamp, "a" * 32)
        self.assertEqual(str(name), "HA_Kuche_Test_2026-11-26_12-02_" + "a" * 32 + ".tar")
        self.assertEqual(len(name.parts), 1)

    def test_empty_reserved_and_long_profile_names(self):
        now = datetime(2026, 11, 26, 12)
        for profile in ("../..", "CON", "", "X" * 1000, "☀"):
            name = str(backup_filename(profile, now, "a" * 32))
            self.assertTrue(name.startswith("HA_"))
            self.assertNotIn("..", name)
            self.assertLess(len(name), 160)

    def test_same_minute_and_sanitized_profiles_remain_distinct(self):
        now = datetime(2026, 11, 26, 12)
        first = backup_filename("Full/Test", now, "a" * 32)
        second = backup_filename("Full:Test", now, "b" * 32)
        self.assertNotEqual(first, second)


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
                    self.assertTrue(str(options.filename).startswith("HA_Full_Test_2026-11-26_12-02_"))
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
