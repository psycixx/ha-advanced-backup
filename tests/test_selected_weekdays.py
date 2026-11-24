"""Schedule tests which do not require Home Assistant."""
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
for name in ("const", "schedule", "models"):
    spec = importlib.util.spec_from_file_location(
        f"advanced_backup_manager.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from advanced_backup_manager.const import *
from advanced_backup_manager.models import validate_profile
from advanced_backup_manager.schedule import is_due


class SelectedWeekdaysTests(unittest.TestCase):
    def _profile(self, weekdays):
        return validate_profile(
            {
                CONF_PROFILE_NAME: "Weekday plan",
                CONF_BACKUP_TYPE: BACKUP_FULL,
                CONF_TIME: "03:00",
                CONF_SCHEDULE: SCHEDULE_WEEKDAYS,
                CONF_WEEKDAYS: weekdays,
                CONF_RETENTION: 3,
                CONF_LOCATION: ".local",
            }
        )

    def test_multiple_weekdays_are_valid(self):
        self.assertEqual(self._profile(["0", "2", "4"])[CONF_WEEKDAYS], [0, 2, 4])

    def test_at_least_one_weekday_is_required(self):
        with self.assertRaisesRegex(ValueError, "invalid_weekdays"):
            self._profile([])

    def test_plan_is_due_on_each_selected_weekday(self):
        profile = self._profile([0, 2])
        self.assertTrue(is_due(profile, datetime(2026, 11, 23, 3, 0), None))
        self.assertFalse(is_due(profile, datetime(2026, 11, 24, 3, 0), None))
        self.assertTrue(is_due(profile, datetime(2026, 11, 25, 3, 0), None))
