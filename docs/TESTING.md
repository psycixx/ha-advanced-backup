# Testnachweis

## Automatisierte Prüfungen

python -m unittest discover -s tests -v prüft Profile, Planung, Dateinamen mit
lokaler Zeit und problematischen Profilnamen, mehrere Starts in derselben Minute,
Optionen für Voll-/Teilbackups an lokale und Netzwerkziele, Speicherung des Intents
vor dem Supervisor-Aufruf, alte Intents ohne Dateiname und Aufbewahrung nach Slug
und Speicherziel.

Zusätzliche Tests für 0.2.14 prüfen fortlaufende Dateinamen nach Neustarts,
Kollisionen durch Bereinigung und Groß-/Kleinschreibung, getrennte Speicherziele,
alte Zustände ohne Zähler, Abbruch vor dem Backup bei fehlgeschlagener Speicherung
sowie deutsche und englische Erfolgsmeldungen mit lokaler Erstellungszeit.

Runner-Tests ersetzen Home-Assistant-Dienste und Supervisor-Aufrufe. GitHub Actions
installiert aiohasupervisor 0.8.1 unter Python 3.13. Ein zusätzlicher Test prüft
dessen tatsächliche JSON-Serialisierung für beide Backup-Typen. Ohne installiertes
SDK laufen die übrigen Tests mit Ersatzobjekten; der SDK-Test wird übersprungen.
compileall prüft die Integrationssyntax. HACS und Hassfest laufen separat in CI.

## Grenzen

Diese Tests erzeugen keine echten Backups und stellen nichts wieder her.
Die Prüfung der vier am 26.11.2026 bereitgestellten Archive betraf ABM 0.2.12,
nicht die neue Dateinamen-Funktion. Optionen für lokale und Netzwerkziele werden
automatisiert geprüft. Echte Schreibvorgänge auf beiden Speicherarten und Neustarts
während eines Backups sind damit nicht nachgewiesen.

Für einen ergänzenden Test auf einer separaten HA-Testinstanz: Voll-/Teilbackups
auf beiden Zielarten erzeugen, zweimal in derselben Minute starten und danach
Wiederaufnahme/Aufbewahrung beobachten. Produktive Backups werden nicht verändert.
