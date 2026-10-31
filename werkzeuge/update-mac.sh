#!/bin/sh
# JARVIS-Update für Noahs Mac.
# Ablauf: neueste GitHub-ZIP aus Downloads holen → nach ~/JARVIS/updates (mit Datum) → nur das Programm
# ersetzen (jarvis/, docs/, tests/, werkzeuge/, config/persona.md). NIE angefasst: data/, .env, config/jarvis.json.
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
NAME="JARVIS-Update_$(date +%Y-%m-%d_%H-%M).zip"
mv "$ZIP" "$UPDATES/$NAME" || exit 1
TMP="$HOME/JARVIS/.update-tmp"
rm -rf "$TMP" && mkdir -p "$TMP"
unzip -q "$UPDATES/$NAME" -d "$TMP" || { echo "ZIP ließ sich nicht entpacken. Nichts geändert."; rm -rf "$TMP"; exit 1; }
QUELLE=$(ls -d "$TMP"/jarvis-* 2>/dev/null | head -1)
if [ -z "$QUELLE" ] || [ ! -f "$QUELLE/jarvis/__init__.py" ]; then
  echo "Die ZIP enthält kein JARVIS. Nichts geändert."; rm -rf "$TMP"; exit 1
fi

for teil in jarvis docs tests werkzeuge; do
  [ -d "$QUELLE/$teil" ] && cp -R "$QUELLE/$teil" "$ZIEL/"
done
[ -f "$QUELLE/config/persona.md" ] && cp "$QUELLE/config/persona.md" "$ZIEL/config/"
[ -f "$QUELLE/config/jarvis.example.json" ] && cp "$QUELLE/config/jarvis.example.json" "$ZIEL/config/"
rm -rf "$TMP"

echo "Update eingespielt: $NAME"
grep __version__ "$ZIEL/jarvis/__init__.py"
echo "Deine Daten, dein Schlüssel und deine Einstellungen wurden nicht verändert."
echo "Starten mit:  cd ~/JARVIS/jarvis-nj && python3 -m jarvis web"
