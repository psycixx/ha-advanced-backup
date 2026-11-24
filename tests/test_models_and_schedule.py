"""Unit tests intentionally independent of Home Assistant imports."""
import importlib.util
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "advanced_backup_manager"
package = types.ModuleType("advanced_backup_manager")
package.__path__ = [str(ROOT)]
sys.modules["advanced_backup_manager"] = package
for name in ("const", "models", "schedule"):
    spec = importlib.util.spec_from_file_location(f"advanced_backup_manager.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from advanced_backup_manager.const import *
from advanced_backup_manager.models import validate_profile
from advanced_backup_manager.schedule import is_due

def profile(**changes):
    base = {CONF_PROFILE_NAME: "Daily", CONF_BACKUP_TYPE: BACKUP_PARTIAL, CONF_TIME: "03:00", CONF_SCHEDULE: SCHEDULE_DAILY, CONF_RETENTION: 2, CONF_ADDON_MODE: ADDON_EXCLUDE, CONF_ADDONS: [], CONF_INCLUDE_HOMEASSISTANT: True, CONF_EXCLUDE_DATABASE: True}
    return base | changes

class ProfileTests(unittest.TestCase):
    def test_full_forces_database_inclusion(self):
        self.assertFalse(validate_profile(profile(**{CONF_BACKUP_TYPE: BACKUP_FULL}))[CONF_EXCLUDE_DATABASE])
    def test_database_needs_homeassistant(self):
        with self.assertRaises(ValueError): validate_profile(profile(**{CONF_INCLUDE_HOMEASSISTANT: False, CONF_EXCLUDE_DATABASE: False}))
    def test_weekdays_need_value(self):
        with self.assertRaises(ValueError): validate_profile(profile(**{CONF_SCHEDULE: SCHEDULE_WEEKDAYS, CONF_WEEKDAYS: []}))
    def test_password_is_retained_as_profile_secret(self):
        self.assertEqual(validate_profile(profile(**{CONF_PASSWORD: "a-long-test-secret"}))[CONF_PASSWORD], "a-long-test-secret")

class ScheduleTests(unittest.TestCase):
    def test_daily_only_once_and_after_time(self):
        p = profile(); now = datetime.fromisoformat("2026-11-24T03:00:00")
        self.assertTrue(is_due(p, now, None))
        self.assertFalse(is_due(p, now, "2026-11-24"))
        self.assertFalse(is_due(p, datetime.fromisoformat("2026-11-24T02:59:00"), None))
    def test_weekday_and_interval_are_calendar_anchored(self):
        monday = datetime.fromisoformat("2026-11-23T04:00:00")
        self.assertTrue(is_due(profile(**{CONF_SCHEDULE: SCHEDULE_WEEKDAYS, CONF_WEEKDAYS: [0]}), monday, None))
        interval = profile(**{CONF_SCHEDULE: SCHEDULE_INTERVAL, CONF_INTERVAL_DAYS: 3, CONF_ANCHOR_DATE: "2026-11-20"})
        self.assertTrue(is_due(interval, datetime.fromisoformat("2026-11-23T04:00:00"), None))
        self.assertFalse(is_due(interval, datetime.fromisoformat("2026-11-24T04:00:00"), None))

if __name__ == "__main__":
    unittest.main()
