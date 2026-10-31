#!/bin/sh
# JARVIS-Update für Noahs Mac.
# Ablauf: neueste GitHub-ZIP aus Downloads holen → nach ~/JARVIS/updates (mit Datum) → nur das Programm
# ersetzen (jarvis/, docs/, tests/, werkzeuge/, config/persona.md, STAND.txt). NIE angefasst: data/, .env, config/jarvis.json.
# Aufruf:  sh ~/JARVIS/jarvis-nj/werkzeuge/update-mac.sh

ZIEL="$HOME/JARVIS/jarvis-nj"
UPDATES="$HOME/JARVIS/updates"

ZIP=$(ls -t "$HOME/Downloads"/jarvis-aktuell*.zip "$HOME/Downloads"/jarvis-version5-3*.zip 2>/dev/null | head -1)
if [ -z "$ZIP" ]; then
  echo "Keine neue JARVIS-ZIP in Downloads gefunden."
  echo "Bitte zuerst herunterladen: https://github.com/nj-31-12/jarvis/archive/refs/heads/aktuell.zip"
  exit 1
fi
if [ ! -d "$ZIEL/jarvis" ] || [ ! -d "$ZIEL/data" ]; then
  echo "Abbruch: $ZIEL sieht nicht wie dein JARVIS-Ordner aus (jarvis/ oder data/ fehlt). Nichts geändert."
  exit 1
fi

mkdir -p "$UPDATES"
TMP="$HOME/JARVIS/.update-tmp"
rm -rf "$TMP" && mkdir -p "$TMP"
unzip -q "$ZIP" -d "$TMP" || { echo "ZIP ließ sich nicht entpacken. Nichts geändert."; rm -rf "$TMP"; exit 1; }
QUELLE=$(ls -d "$TMP"/jarvis-* 2>/dev/null | head -1)
if [ -z "$QUELLE" ] || [ ! -f "$QUELLE/jarvis/__init__.py" ]; then
  echo "Die ZIP enthält kein JARVIS. Nichts geändert."; rm -rf "$TMP"; exit 1
fi
# Strukturierter Name: JARVIS_<Nummer>_<Datum>_<Inhalt>.zip (aus STAND.txt der neuen Version)
STAND=$(head -1 "$QUELLE/STAND.txt" 2>/dev/null | tr -cd 'A-Za-z0-9._-')
[ -z "$STAND" ] && STAND="ohne-Nummer_$(date +%Y-%m-%d_%H-%M)"
ALT=$(head -1 "$ZIEL/STAND.txt" 2>/dev/null | tr -cd 'A-Za-z0-9._-')
NAME="JARVIS_${STAND}.zip"
[ -e "$UPDATES/$NAME" ] && NAME="JARVIS_${STAND}_erneut-$(date +%H-%M).zip"
mv "$ZIP" "$UPDATES/$NAME" || { rm -rf "$TMP"; exit 1; }

for teil in jarvis docs tests werkzeuge; do
  [ -d "$QUELLE/$teil" ] && cp -R "$QUELLE/$teil" "$ZIEL/"
done
[ -f "$QUELLE/config/persona.md" ] && cp "$QUELLE/config/persona.md" "$ZIEL/config/"
[ -f "$QUELLE/config/jarvis.example.json" ] && cp "$QUELLE/config/jarvis.example.json" "$ZIEL/config/"
[ -f "$QUELLE/STAND.txt" ] && cp "$QUELLE/STAND.txt" "$ZIEL/"
rm -rf "$TMP"

echo "Vorher:  ${ALT:-unbekannt}"
echo "Jetzt:   $STAND"
echo "Abgelegt als: ~/JARVIS/updates/$NAME"
echo "Deine Daten, dein Schlüssel und deine Einstellungen wurden nicht verändert."
echo "Starten mit:  cd ~/JARVIS/jarvis-nj && python3 -m jarvis web"
