# Testnachweis

## Enthaltene lokale Tests

`python -m unittest discover -s tests -v` prüft reine, deterministische Einheiten:

- Profilvalidierung einschließlich der MariaDB-Regel für Teilbackups;
- tägliche, Wochentags- und kalenderverankerte N-Tages-Planung;
- keine doppelte Ausführung am selben Datum und kein Nachholen vor der Uhrzeit.

Zusätzlich prüft `compileall` die Python-Syntax aller Integrationsdateien. Diese
Tests benötigen keine Home-Assistant-Instanz und führen keine Backups aus.

**Ausführungsstand:** In dieser Windows-Arbeitsumgebung war beim ersten Versuch
kein Python-Interpreter im `PATH` verfügbar. Die Ausführung wird daher erst nach
dem Push durch die beigefügte GitHub-Action nachgewiesen; es wird nicht behauptet,
dass hier lokal Tests gelaufen sind.

## Vor HACS-Freigabe auf separater HA-OS-Testinstanz erforderlich

1. Konfigurations- und Optionsdialog gegen die konkrete HA-Version testen.
2. Teilbackup mit Datenbank-Ausschluss: Detail muss `homeassistant_exclude_database=true` zeigen.
3. Vollbackup erzeugen und MariaDB-Einschluss bestätigen.
4. Ein verschlüsseltes Teil- und Vollbackup erzeugen; Wiederherstellungsdialog
   muss das Passwort verlangen und mit falschem Passwort scheitern.
5. Include- und Exclude-Modus testen, einschließlich eines später installierten Add-ons.
6. Zwei Profile gleichzeitig starten: eines muss ohne Warteschlange abgelehnt werden.
7. Während eines Aufrufs HA neu starten: Sperre und `resolve_uncertain` testen.
8. Mehr Erfolge als Aufbewahrung erzeugen; nur bekannte eigene lokale Slugs dürfen gelöscht werden.
9. Sommer-/Winterzeit und Neustart nahe Termin testen.

Keiner dieser Tests darf auf einer produktiven Instanz erfolgen.
