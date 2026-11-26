# Architektur

## Sicherungsumfang und Verschlüsselung

Jeder Konfigurationseintrag ist ein Profil. Vollbackups verwenden die reguläre
Supervisor-Funktion full_backup mit Datenbank-Einschluss. Teilbackups übergeben
App-Auswahl, HA-Auswahl und Datenbankoption an partial_backup. Separate Ordner
werden bei Teilbackups derzeit nicht angefordert. Im Exclude-Modus wird die
installierte App-Liste vor jedem Lauf neu gelesen. MariaDB als App und die
HA-Datenbankoption sind getrennte Bestandteile des Sicherungsumfangs.

ABM verwendet ausschließlich den zentralen Backup-Schlüssel von Home Assistant.
Er wird an Supervisor übergeben und nicht als eigener Profilschlüssel gespeichert.
Fehlt er, wird der Lauf vor dem Supervisor-Aufruf abgelehnt. Schlüsselwerte werden
nicht in Ereignissen, Sensoren oder Meldungen ausgegeben. Der bekannte Core-Fehler
beim Entschlüsseln von apps_local ist im README mit upstream Links dokumentiert.

## Dateinamen

Neue Archive heißen HA_<Profil>_<JJJJ-MM-TT>_<HH-MM>.tar. Weitere Reservierungen
für denselben bereinigten Namen und dasselbe Ziel erhalten _02, _03 usw. Die
Zähler stehen global unter filename_counters und werden gemeinsam mit dem Intent
vor dem Supervisor-Aufruf gespeichert. Alte Zustände erhalten ein leeres Mapping;
bestehende Intents bleiben gültig. Reservierungen werden nach Fehlern oder nach
Aufbewahrungs-Löschungen nicht zurückgesetzt. Fehlversuche können Nummernlücken
hinterlassen. Groß-/Kleinschreibung wird bei der Kollisionserkennung ignoriert.

Der interne Name behält seine UUID-Kennung zur Wiederaufnahme. Die Option filename
wird als PurePath an beide Backup-Typen und Speicherarten übergeben. Vorhandene
Archive werden nicht umbenannt. Supervisor lehnt bereits vorhandene Zieldateien
ab; ABM überschreibt auch bei einem zurückgespielten alten Zähler keine Archive.

## Erfolgsmeldungen

Nach bestätigtem Erfolg zeigt die Meldung Profil, Sicherungstyp und lokale
Erstellungszeit aus dem bestätigten Backup. Technische IDs werden nur intern für
Ereignisse, Statusattribute und Wiederaufnahme verwendet. Die konfigurierte
HA-Sprache bestimmt Deutsch oder den englischen Standardtext. Deaktivierte
Erfolgsmeldungen bleiben deaktiviert; Fehlerbenachrichtigungen bleiben unverändert.

## Ausführung und Wiederaufnahme

Alle Profile teilen ein asyncio.Lock. Ein manueller Start während eines ABM-Laufs
wird abgelehnt. Fällige geplante Profile werden bei späteren Minuten-Ticks erneut
berücksichtigt. Pro Tick beginnt höchstens ein Lauf.

Vor dem Supervisor-Aufruf wird ein Intent mit Profil, internem Namen, Dateiname,
Ziel und geplantem Datum gespeichert. Der Aufruf wartet mit background=False.
Erst ein Rückgabe-Slug und ein Detailabruf mit dem erwarteten Ziel gelten als Erfolg.

Bei unbekanntem Ausgang bleibt der Intent erhalten. Der nächste Tick sucht genau
ein Backup mit identischem internem Namen und bestätigt dessen Ziel. Das gilt auch
für alte Intents ohne Dateiname. Bleibt die Zuordnung unklar, ist eine manuelle
Auflösung erforderlich. Explizite Freeze-Ablehnungen vor der Ausführung führen bei
geplanten Läufen zu höchstens drei Versuchen im Abstand von fünf Minuten.

## Planung und Aufbewahrung

Die Planung verwendet lokale HA-Zeit und feste Kalendertage. Bestätigte geplante
Termine werden nicht doppelt ausgeführt. Frühere Tage werden nicht nachgeholt;
neue Profile holen bereits verstrichene Termine desselben Tages ebenfalls nicht nach.

Nach Erfolg werden nur ältere, vom Profil aufgezeichnete Backups anhand ihres
Slugs am gespeicherten Ziel gelöscht. Das jüngste bestätigte eigene Backup bleibt
erhalten. Dateinamen spielen bei Wiederaufnahme und Aufbewahrung keine Rolle.

## API-Grundlage

Core 2026.11.0 und 2026.11.3 verwenden aiohasupervisor 0.8.1. FullBackupOptions
unterstützt filename als PurePath; PartialBackupOptions erbt diese Option.
Supervisor 2026.11.0 akzeptiert sie für beide Backup-Typen.

- https://github.com/home-assistant-libs/python-supervisor-client/tree/aa4eec3403cb942b3acf1c87c41be1359bf02877
- https://github.com/home-assistant/supervisor/blob/2026.11.0/supervisor/api/backups.py
