# Projekt-Lektionen (für Noah, Claude und ChatGPT)

Claude hat kein Gedächtnis über Gespräche hinweg. Diese Datei hält fest, was bei der Entwicklung schiefging,
damit es nicht wieder passiert. Persönliche Lektionen für JARVIS selbst legt Noah im Second Brain an.

| Datum | Was passiert ist | Regel ab jetzt |
|---|---|---|
| 31.10.2026 | GitHub-ZIP vom Zweig `main` (5.2) statt `version5-3` geladen | Immer den direkten Link zum Zweig geben: `…/archive/refs/heads/<zweig>.zip`. Nach jedem Download mit `grep __version__ jarvis/__init__.py` prüfen. |
| 31.10.2026 | `cp -a …/data ziel/` hat, weil `ziel` fehlte, den Datenordner **als** `ziel` angelegt | Vor dem Kopieren prüfen, dass der Zielordner existiert, oder Umbenennen und Kopieren in einem geprüften Befehl erledigen. |
| 31.10.2026 | API-Schlüssel war auf einem Bildschirmfoto sichtbar | Nie Fotos von Schlüssel-Fenstern schicken. Falls doch: Schlüssel sofort in der Console löschen und neu anlegen. |
| 31.10.2026 | Alte Terminal-Ausgabe statt des Befehls eingefügt | Vor jedem Befehl `cmd + K`, nur den grauen Befehlskasten kopieren. |
| 31.10.2026 | Ein Freigabe-Fenster bei GitHub zeigte „Authorized“, nicht „Installed“ | Für Schreibzugriff muss die Claude-App unter „Installed GitHub Apps“ stehen. |
| 31.10.2026 | Alte Daten verlangten beim Start eine Umstellung (`action_meta`) | Ist gewollt (keine stille Umstellung). Mit „ja“ bestätigen, vorher wird gesichert. |
| 31.10.2026 | Update-ZIP fehlte bzw. hieß „(1).zip“, Downloads unübersichtlich | Ordnung in `~/JARVIS` (jarvis-nj, rueckfall, updates, archiv). Updates nur noch mit `werkzeuge/update-mac.sh`, das die neueste ZIP selbst findet. |
| 01.11.2026 | Wunsch nach Wake-Word widersprach der Roadmap-Regel „nie Dauerzuhören“ | Regeländerungen nur mit Noahs ausdrücklicher Entscheidung, dokumentiert in docs/24 (Standard AUS). |
