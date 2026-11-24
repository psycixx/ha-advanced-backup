""""Pure profile validation shared by config flow and runner."""
from __future__ import annotations

from datetime import date, time
from typing import Any

from .const import *


def validate_profile(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate an MVP profile without Home Assistant imports."""
    result = dict(data)
    if not str(result.get(CONF_PROFILE_NAME, "")).strip():
        raise ValueError("profile_name_required")
    if result.get(CONF_BACKUP_TYPE) not in (BACKUP_FULL, BACKUP_PARTIAL):
        raise ValueError("invalid_backup_type")
    try:
        time.fromisoformat(str(result[CONF_TIME]))
    except (KeyError, ValueError) as err:
        raise ValueError("invalid_time") from err
    schedule = result.get(CONF_SCHEDULE)
    if schedule not in (SCHEDULE_DAILY, SCHEDULE_WEEKDAYS, SCHEDULE_INTERVAL):
        raise ValueError("invalid_schedule")
    if schedule == SCHEDULE_WEEKDAYS:
        weekday_values = result.get(CONF_WEEKDAYS, [])
        if isinstance(weekday_values, (str, int)):
            weekday_values = [weekday_values]
        try:
            weekdays = {int(day) for day in weekday_values}
        except (TypeError, ValueError) as err:
            raise ValueError("invalid_weekdays") from err
        if not weekdays or not weekdays <= set(range(7)):
            raise ValueError("invalid_weekdays")
        result[CONF_WEEKDAYS] = sorted(weekdays)
    if schedule == SCHEDULE_INTERVAL:
        try:
            interval = int(result[CONF_INTERVAL_DAYS])
            date.fromisoformat(str(result[CONF_ANCHOR_DATE]))
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError("invalid_interval") from err
        if interval < 1 or interval > 366:
            raise ValueError("invalid_interval")
        result[CONF_INTERVAL_DAYS] = interval
    retention = int(result.get(CONF_RETENTION, 1))
    if retention < 1 or retention > 365:
        raise ValueError("invalid_retention")
    result[CONF_RETENTION] = retention
    result[CONF_ADDONS] = sorted(set(result.get(CONF_ADDONS, [])))
    result[CONF_LOCATION] = str(result.get(CONF_LOCATION, ".local")) or ".local"
    result[CONF_NOTIFY_SUCCESS] = bool(result.get(CONF_NOTIFY_SUCCESS, False))
    result[CONF_NOTIFY_FAILURE] = bool(result.get(CONF_NOTIFY_FAILURE, True))
    password = result.get(CONF_PASSWORD)
    if password is not None and not isinstance(password, str):
        raise ValueError("invalid_password")
    result[CONF_PASSWORD] = password or None
    if result.get(CONF_ADDON_MODE, ADDON_INCLUDE) not in (
        ADDON_INCLUDE,
        ADDON_EXCLUDE,
    ):
        raise ValueError("invalid_addon_mode")
    if result[CONF_BACKUP_TYPE] == BACKUP_FULL:
        result[CONF_EXCLUDE_DATABASE] = False
    elif (
        not result.get(CONF_INCLUDE_HOMEASSISTANT, True)
        and result.get(CONF_EXCLUDE_DATABASE) is False
    ):
        raise ValueError("database_requires_homeassistant")
    return result
