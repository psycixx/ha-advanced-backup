"""Calendar anchored schedule decisions."""
from __future__ import annotations
from datetime import datetime, date, time
from typing import Any
from .const import *

def is_due(data: dict[str, Any], now: datetime, last_scheduled_date: str | None) -> bool:
    """Return true once for the current local date, never catching up prior dates."""
    today = now.date()
    if last_scheduled_date == today.isoformat() or now.timetz().replace(tzinfo=None) < time.fromisoformat(data[CONF_TIME]):
        return False
    schedule = data[CONF_SCHEDULE]
    if schedule == SCHEDULE_DAILY:
        return True
    if schedule == SCHEDULE_WEEKDAYS:
        return today.weekday() in data[CONF_WEEKDAYS]
    anchor = date.fromisoformat(data[CONF_ANCHOR_DATE])
    return today >= anchor and (today - anchor).days % data[CONF_INTERVAL_DAYS] == 0
