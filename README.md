# Advanced Backup Manager

Independent scheduled Supervisor backup profiles for Home Assistant OS/Supervised.

## Install through HACS
1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/psycixx/ha-advanced-backup` with category **Integration**.
3. Find the repository in HACS, select **Download**, and restart Home Assistant.
4. Add the integration under **Settings → Devices & services**.

## Features
- Daily, weekday, and calendar-anchored interval schedules.
- Full or partial backups, add-on include/exclude, and optional database exclusion.
- Per-profile retention: only confirmed backups created by that profile are pruned, and the newest confirmed one is always retained.
- Choose local storage or any active Supervisor backup mount, including NAS Backup Storage locations.
- Optional profile password and optional English system-wide success/failure notifications.
- Global serialization and a deliberate manual-resolution lock for uncertain runs.

## Install and configure
1. Install `custom_components/advanced_backup_manager` and restart Home Assistant.
2. Add one integration entry per profile.
3. Choose an active backup location, schedule, contents, and **Backups to retain**.
4. Run the profile once manually and confirm it on **Settings → System → Backups** before enabling schedules.

## Safety
A possibly side-effecting Supervisor call first records a durable intent. If its outcome is uncertain, all further profile runs stop until an administrator inspects the Supervisor and calls `advanced_backup_manager.resolve_uncertain`. Passwords are not shown in later edits or sensors, but scheduled profiles must be stored in Home Assistant configuration storage. Test restoration before production use.
