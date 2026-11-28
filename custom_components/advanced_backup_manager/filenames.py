"""Portable archive filenames for new Supervisor backups."""

from datetime import datetime
from pathlib import PurePath
import re
import unicodedata


def backup_filename(profile_name: str, now: datetime, run_id: str) -> PurePath:
    """Keep names readable and distinguish runs in the same local minute.

    The run ID is generated once for both the internal backup name and filename.
    A unique suffix also separates profiles whose names sanitize to the same text.
    Existing archives are never renamed or selected as an overwrite target.
    """
    ascii_name = unicodedata.normalize("NFKD", profile_name).encode(
        "ascii", "ignore"
    ).decode()
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_name).strip("_-")
    safe_name = safe_name[:80].rstrip("_-") or "Backup"
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("run_id must be a UUID hex string")
    return PurePath(f"HA_{safe_name}_{now:%Y-%m-%d_%H-%M}_{run_id}.tar")
