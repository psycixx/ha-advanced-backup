# Architektur

## Profile

Jeder Konfigurationseintrag ist ein Profil. Ein Profil hat Typ, lokale Uhrzeit,
Kalenderregel, Add-on-Auswahl, Datenbankoption und Aufbewahrung. Änderungen
erfolgen im nativen Optionsdialog. Bei `exclude` wird die aktuelle Supervisor-
Inventarliste unmittelbar vor jedem Teilbackup gelesen: neu installierte Add-ons
werden daher automatisch eingeschlossen, sofern sie nicht explizit ausgeschlossen
sind.

Ein Vollbackup ruft `BackupsClient.full_backup()` auf und enthält zwangsläufig
alles, auch MariaDB. Ein Teilbackup ruft `partial_backup()` auf und übergibt
`homeassistant_exclude_database=True`, wenn die Datenbank ausgeschlossen ist.

## Verschlüsselung

Ein optionales Passwort pro Profil wird als `FullBackupOptions.password` bzw.
`PartialBackupOptions.password` an den Supervisor übergeben. Damit setzt der
Supervisor das geschützte Backup-Format um; beim Wiederherstellen ist dasselbe
Passwort erforderlich. Es wird weder geloggt noch über Events oder Sensoren
offengelegt. Weil geplante Backups nicht nach einem interaktiven Geheimnis fragen
können, speichert HA das Passwort im Config-Entry unter `.storage`. Diese Datei
ist nicht automatisch ein Geheimnisspeicher und kein Ersatz für den Schutz des
HA-Konfigurationslaufwerks. In einem Optionsdialog wird
das bestehende Passwort nie zurückgegeben; ein leeres Feld behält es bei.

## Ausführung und Absturzschutz

Alle Profile teilen einen `asyncio.Lock`. Ist er belegt, wird ein manueller Start
abgelehnt; geplante Starts werden nicht nachgereicht. Das vermeidet eine
unbegrenzte Warteschlange. Der Supervisor-Aufruf verwendet `background=False`.
Erst ein nichtleerer Rückgabe-Slug **und** ein erfolgreicher `backup_info`-Abruf
gelten als Erfolg.

Vor dem Aufruf wird `intent` in `.storage/advanced_backup_manager.state`
geschrieben. Bei jedem Fehler bleibt dieses Intent bestehen und sperrt alle
weiteren Ausführungen — auch nach einem Neustart. Der Administrator muss den
Supervisor kontrollieren und mit `resolve_uncertain` bestätigen. Das MVP kann
einen möglicherweise entstandenen, aber nicht identifizierten Backup-Slug nicht
sicher einem Profil zuordnen und löscht ihn deshalb nie.

## Planung

Ein Zeit-Listener bewertet die lokale HA-Zeit minutengenau. Ein Datum wird nur
einmal ausgeführt. Intervallregeln rechnen `(heutiges lokales Datum - Stichtag) %
N`; manuelle Starts verändern diese Verankerung nicht. Nachgeholt wird maximal am
aktuellen Kalendertag: frühere, verpasste Tage werden nicht rückwirkend erzeugt.
Bei doppelten DST-Zeitpunkten verhindert `last_scheduled_date` die zweite
Ausführung; bei nicht existierender Uhrzeit im Frühling erfolgt keine künstliche
Nachholung.

## Aufbewahrung

Nur nach bestätigtem Erfolg wird der Slug in der persistenten, profilspezifischen
Liste erfasst. Nach einem neuen Erfolg werden ausschließlich darin enthaltene,
ältere Backups gelöscht. Vor dem Löschen wird erneut `backup_info` geprüft. Das
jüngste eigene Backup bleibt immer erhalten. Der MVP setzt `location=.local` und
löscht daher keine Kopien auf Netzspeichern oder Cloud-Zielen.

## API-Grundlage

Gegen Home Assistant Core **2026.11.3** geprüft: die Core-Services erzeugen
`FullBackupOptions` bzw. `PartialBackupOptions` über den authentifizierten
`get_supervisor_client`, warten auf den Client-Aufruf und liefern den Slug zurück.
Die Supervisor-Dokumentation beschreibt `background=false` als wartend und
`GET /backups/<slug>/info` als Detailprüfung.

- https://github.com/home-assistant/core/blob/2026.11.3/homeassistant/components/hassio/services.py
- https://contributors.home-assistant.io/apps/supervisor-api/backups/
