"""Readable notification text without technical backup identifiers."""

from datetime import datetime


def success_notification(
    profile_name: str, backup_type: str, created_at: datetime, language: str
) -> tuple[str, str]:
    """Format the confirmed backup's creation time in Home Assistant local time."""
    if language.split("-", 1)[0].lower() == "de":
        kind = "Vollbackup" if backup_type == "full" else "Teilbackup"
        return (
            f"Backup erfolgreich: {profile_name}",
            f"{kind} vom {created_at:%d.%m.%Y} um {created_at:%H:%M} Uhr wurde erstellt.",
        )
    kind = "Full backup" if backup_type == "full" else "Partial backup"
    return (
        f"Backup successful: {profile_name}",
        f"{kind} created on {created_at:%Y-%m-%d} at {created_at:%H:%M}.",
    )
