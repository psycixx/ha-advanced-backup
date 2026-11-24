# Advanced Backup Manager

Eine Home-Assistant-Custom-Integration fuer mehrere, unabhaengige Supervisor-Backup-Profile.

## MVP installieren (nur HA OS / Supervisor)

1. Den Ordner `custom_components/advanced_backup_manager` nach
   `<config>/custom_components/advanced_backup_manager` kopieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Advanced Backup
   Manager**. Pro Profil einen Eintrag anlegen.
4. Fuer den genannten Anwendungsfall zwei Profile anlegen: ein *Teilbackup* mit
   `Datenbank ausschließen` sowie ein *Vollbackup* alle drei Tage. Ein Vollbackup
   enthält immer die Datenbank.

Optional kann jedes Profil ein eigenes Verschlüsselungspasswort erhalten. Dieses
Passwort muss beim Wiederherstellen des jeweiligen Backups eingegeben werden.
Das Passwortfeld bleibt bei späteren Bearbeitungen leer; leer lassen bedeutet,
dass das vorhandene Passwort beibehalten wird.

Nach der Einrichtung stehen pro Profil ein Statussensor und die Dienste
`advanced_backup_manager.run` sowie `advanced_backup_manager.resolve_uncertain`
zur Verfügung.

## Sicherheitsmodell und Grenzen

Die Integration nutzt ausschließlich den in HA authentifizierten Supervisor-Client.
Sie funktioniert nicht mit Home Assistant Container oder Core. Backups werden im
MVP nur am lokalen Supervisor-Speicherort (`.local`) erzeugt. Ein optionales
profilbezogenes Supervisor-Passwort schützt ein Backup kryptografisch; es liegt
für die automatische Ausführung in Home Assistants lokalem `.storage` vor.
Wer Zugriff auf das HA-Konfigurationsdateisystem hat, ist deshalb als
vertrauenswürdig zu behandeln. Es gibt keine Uploads, Wiederherstellungen oder
Verwaltung fremder Backups.

Vor dem API-Aufruf wird eine Ausführungsabsicht persistent gespeichert. Bricht HA
während oder nach dem Aufruf ab oder kommt eine API-Antwort nicht eindeutig an,
bleibt das Profil blockiert. Das ist absichtlich: erst im Supervisor prüfen, ob ein
Backup entstanden ist, und dann den Status über `resolve_uncertain` bestätigen.
Es werden nie automatische Wiederholungen ausgeführt. Auch fehlgeschlagene
Ausführungen loesen keine Aufbewahrungsloeschung aus.

Details und Testnachweise stehen in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
und [docs/TESTING.md](docs/TESTING.md).
