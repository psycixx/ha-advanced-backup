# Advanced Backup Manager

Independent scheduled Supervisor backup profiles for Home Assistant OS/Supervised.

> [!IMPORTANT]
> **Restart Home Assistant after installing or updating this integration in HACS.** New custom integrations and their configuration flows are loaded only during Home Assistant startup. Do not try to add the integration before the restart has completed.

## Install through HACS

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/psycixx/ha-advanced-backup` with category **Integration**.
3. Find the repository in HACS and select **Download**.
4. **Restart Home Assistant.**
5. Add the integration under **Settings → Devices & services**.

## Features

- Daily, interval, and freely selected-weekday schedules.
- An interval starts from a chosen date and can represent weekly, monthly, or any other N-day cadence.
- Full or partial backups, add-on include/exclude, and optional database exclusion.
- Per-profile retention: only confirmed backups created by that profile are pruned, and the newest confirmed one is always retained.
- Choose local storage or any active Supervisor backup mount, including Network Storage Manager locations.
- All plans use Home Assistant's central backup encryption key.
- Optional English system-wide success/failure notifications.
- Global serialization and a deliberate manual-resolution lock for uncertain runs.

## Install and configure

1. Install `custom_components/advanced_backup_manager` and restart Home Assistant.
2. Before running a plan, configure Home Assistant's central backup encryption key under **Settings → System → Backups**. The integration never stores a separate per-plan key.
3. Add one integration entry per profile.
4. Choose an active backup location, a schedule, contents, and **Backups to retain**.
5. Use **Daily**, **Interval**, or **Selected weekdays**. The latter accepts one or more weekdays.
6. Use **Run backup now** to test the profile and confirm the backup under **Settings → System → Backups** before relying on schedules.

## Safety

A possibly side-effecting Supervisor call first records a durable intent. If its outcome is uncertain, all further profile runs stop until an administrator inspects the Supervisor and calls `advanced_backup_manager.resolve_uncertain`. The central encryption key is managed by Home Assistant and is not exposed by this integration. Test restoration before production use.
