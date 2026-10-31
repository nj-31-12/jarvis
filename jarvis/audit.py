"""Manipulationssicheres Protokoll (Audit-Log).

Jeder Eintrag enthält den Hash des vorherigen Eintrags (Hash-Kette).
Wird nachträglich eine Zeile verändert oder gelöscht, fällt das bei verify() auf.

Robustheit (Version 4.2):
- Eine durch Absturz abgeschnittene letzte Zeile blockiert keine weiteren Einträge mehr. Neue Einträge
  beginnen auf einer neuen Zeile und verketten sich mit dem letzten GÜLTIGEN Eintrag. verify() meldet
  die beschädigte Zeile ehrlich, statt abzustürzen.
- Mehrere Programme (z. B. Webserver und Terminal-Befehl) schreiben nacheinander: Dateisperre (flock).
- Der letzte Hash wird zwischengespeichert, damit nicht bei jedem Eintrag die ganze Datei gelesen wird.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

try:                      # macOS und Linux; unter Windows nicht vorhanden (dort nur Thread-Sperre)
    import fcntl
except ImportError:       # pragma: no cover
    fcntl = None

_GENESIS = "0" * 64


def _entry_hash(entry: dict) -> str:
    body = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache = None        # (Dateigröße, letzter gültiger Hash, endet mit Zeilenumbruch)

    # ------------------------------------------------------------------ Lesen
    def _scan(self) -> tuple[str, bool]:
        """Letzter GÜLTIGER Hash und ob die Datei mit einem Zeilenumbruch endet."""
        if not self.path.exists():
            return _GENESIS, True
        last = _GENESIS
        with self.path.open("rb") as fh:
            data = fh.read()
        for raw in data.split(b"\n"):
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line.decode("utf-8"))
                last = entry["hash"]
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                continue          # beschädigte Zeile (z. B. Absturz beim Schreiben) überspringen
        return last, (not data or data.endswith(b"\n"))

    def _last_state(self) -> tuple[str, bool]:
        size = self.path.stat().st_size if self.path.exists() else 0
        if self._cache and self._cache[0] == size:
            return self._cache[1], self._cache[2]
        last, ends_nl = self._scan()
        return last, ends_nl

    # ------------------------------------------------------------------ Schreiben
    def write(self, event: str, **details) -> dict:
        with self._lock:
            fd = os.open(str(self.path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_EX)      # anderes Programm schreibt gerade → warten
                last, ends_nl = self._last_state()
                entry = {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "event": event,
                    "details": details,
                    "prev": last,
                }
                entry["hash"] = _entry_hash(entry)
                line = json.dumps(entry, ensure_ascii=False) + "\n"
                if not ends_nl:
                    line = "\n" + line          # abgeschnittene Zeile abschließen, nicht überschreiben
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
                self._cache = (os.fstat(fd).st_size, entry["hash"], True)
            finally:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            return entry

    # ------------------------------------------------------------------ Prüfen
    def verify(self) -> tuple[bool, str]:
        if not self.path.exists():
            return True, "Noch keine Einträge."
        prev = _GENESIS
        damaged = []
        with self.path.open("rb") as fh:
            lines = fh.read().split(b"\n")
        for n, raw in enumerate(lines, 1):
            if not raw.strip():
                continue
            try:
                entry = json.loads(raw.decode("utf-8"))
                stored = entry.pop("hash")
            except (ValueError, KeyError, TypeError, UnicodeDecodeError, AttributeError):
                damaged.append(n)
                continue
            if entry.get("prev") != prev:
                return False, f"Kette unterbrochen in Zeile {n}"
            if _entry_hash(entry) != stored:
                return False, f"Zeile {n} wurde verändert"
            prev = stored
        if damaged:
            return False, (f"Beschädigte Zeile(n) {', '.join(map(str, damaged))} (z. B. Absturz beim Schreiben). "
                           f"Alle übrigen Einträge sind unverändert und lückenlos verkettet.")
        return True, "Protokoll ist unverändert."

    def tail(self, n: int = 10) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({"ts": "", "event": "BESCHÄDIGTE ZEILE", "details": {}})
        return out[-n:]
