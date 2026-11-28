# Changelog

## 0.2.15 — 2026-11-28

### Compatibility

- Supports Home Assistant Core 2026.10.0 and later. The test matrix validates
  the bundled `aiohasupervisor` 0.6.0 and 0.8.1 APIs.
- Backup creation, storage targets (local and active Supervisor mounts),
  central encryption-key access, retention, and recovery use the same API
  surface on both supported versions.
- Readable custom archive filenames work with both tested Supervisor APIs.
- Home Assistant Cloud Backup is not exposed as an ABM target in this release.
  Profiles can use local storage and active Supervisor backup mounts (including
  NAS locations); use Home Assistant's native Backup interface for Cloud Backup.

### Upgrade

Restart Home Assistant after updating. Existing profiles, backup IDs, storage
locations, retention records, and encryption settings are unchanged. No live
backup or restoration is performed by automated tests.

## 0.2.14 — 2026-11-26

### Improved

- Short archive filenames without random suffixes:
  `HA_<ProfileName>_<YYYY-MM-DD>_<HH-MM>.tar`.
- Additional runs using the same filename and storage target receive `_02`,
  `_03`, etc. Reservations persist before backup creation and survive restarts.
- Success notifications show the profile, full/partial backup type, and local
  creation time instead of the technical backup ID. German and English text
  follows Home Assistant's configured language.
- Updated manifest and project metadata to 0.2.14.

### Validation and upgrade

Automated tests cover numbering across restarts and sanitized/case-insensitive
name collisions, persisted intent, SDK serialization, and success notifications.
Restart Home Assistant after updating. Existing archives keep their names;
internal backup identifiers, recovery, retention, and encryption are unchanged.
No live backup or restoration is performed by these tests. The upstream Core
local-app archive issue documented below remains outside this ABM change.

## 0.2.13 — 2026-11-26

### Added

- Descriptive filenames for new full and partial backups:
  `HA_<ProfileName>_<YYYY-MM-DD>_<HH-MM>_<unique-run-id>.tar`.
- Portable profile names and a unique suffix for repeated runs in the same
  local minute, including profiles whose sanitized names coincide.
- Tests for filename handling, local and network location options, persisted
  intent, recovery, retention, and serialization with the actual Supervisor SDK.

### Updated

- Aligned `manifest.json` and project metadata at version 0.2.13.
- Minimum Home Assistant Core version is now 2026.11.0, whose Supervisor SDK
  supports the filename option for both backup types.
- Refreshed architecture and testing documentation for the central encryption
  key, storage locations, and recovery behavior.

### Known upstream issue

Home Assistant Core 2026.11.3 can leave the local-app source archive encrypted
in a decrypted download and can omit it during per-agent encryption. This is
tracked by [Core #187111](https://github.com/home-assistant/core/issues/187111)
and [ABM #6](https://github.com/psycixx/ha-advanced-backup/issues/6).
The upstream fix is included in 2026.12.0b0; it is not supplied by this ABM release.

### Upgrade

Restart Home Assistant after updating. Existing profiles and archives retain
their settings and names. Recovery and retention continue to use recorded
backup IDs, internal names, and storage locations rather than the new filename.
