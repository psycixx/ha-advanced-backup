"""Portable archive filenames for new Supervisor backups."""

from datetime import datetime
from pathlib import PurePath
import re
import unicodedata


def backup_filename(profile_name: str, now: datetime, sequence: int = 1) -> PurePath:
    """Use a numeric suffix only when a name has already been reserved."""
    ascii_name = unicodedata.normalize("NFKD", profile_name).encode(
        "ascii", "ignore"
    ).decode()
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_name).strip("_-")
    safe_name = safe_name[:80].rstrip("_-") or "Backup"
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    suffix = f"_{sequence:02d}" if sequence > 1 else ""
    return PurePath(f"HA_{safe_name}_{now:%Y-%m-%d_%H-%M}{suffix}.tar")
