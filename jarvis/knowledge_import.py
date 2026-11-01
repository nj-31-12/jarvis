"""Wissenspaket-Import (Stand 17): Markdown-Notizen in das Second Brain übernehmen.

Aufruf:  python3 -m jarvis wissen-import <Ordner oder .zip>
Regeln:
- Nur .md-Dateien, höchstens 300 Dateien und je 200 KB. Pfade aus dem Paket werden nie übernommen (kein ../).
- Ziel ist immer ein NEUER Unterordner in 00_Inbox/JARVIS (dem einzigen Ordner, in den JARVIS ohne Rückfrage schreibt).
- Bestehende Dateien werden nie überschrieben: Gleicher Name → wird übersprungen und gemeldet.
- Dateien mit erkannten sensiblen Daten (Bankdaten, Zugangsdaten …) werden NICHT übernommen.
- Nichts wird gesendet. Der Import ist rein lokal.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from .knowledge import SENSITIVE_PATTERNS

MAX_FILES = 300
MAX_BYTES = 200 * 1024
TARGET = "00_Inbox/JARVIS/Wissenspaket"


def _safe_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^\w .,()&+–-]", "", base, flags=re.UNICODE).strip(" .")
    return (base[:-3] if base.lower().endswith(".md") else base)[:90] or "Notiz"


def _entries(source: Path):
    if source.is_dir():
        for p in sorted(source.rglob("*.md")):
            if p.is_file() and not p.is_symlink():
                yield p.name, (p.read_bytes() if p.stat().st_size <= MAX_BYTES else None)
    elif source.suffix.lower() == ".zip" and source.is_file():
        with zipfile.ZipFile(source) as z:
            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".md") or "__MACOSX" in info.filename:
                    continue
                yield info.filename, (z.read(info) if info.file_size <= MAX_BYTES else None)
    else:
        raise FileNotFoundError("Bitte einen Ordner oder eine .zip-Datei angeben.")


def import_pack(vault, source, folder: str = TARGET) -> dict:
    """Übernimmt das Paket. Gibt {"neu": [...], "vorhanden": [...], "abgelehnt": [(name, grund)]} zurück."""
    source = Path(source).expanduser()
    target_rel = folder.strip("/")
    if not vault.can_auto_write(target_rel + "/x.md"):
        raise PermissionError(f"{target_rel} ist kein freigegebener Entwurfsordner.")
    out = {"neu": [], "vorhanden": [], "abgelehnt": []}
    count = 0
    for name, data in _entries(source):
        count += 1
        if count > MAX_FILES:
            out["abgelehnt"].append((name, f"mehr als {MAX_FILES} Dateien"))
            continue
        if data is None:
            out["abgelehnt"].append((name, "größer als 200 KB"))
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            out["abgelehnt"].append((name, "keine UTF-8-Textdatei"))
            continue
        hits = [label for label, pattern in SENSITIVE_PATTERNS if pattern.search(text)]
        if hits:
            out["abgelehnt"].append((name, "enthält vermutlich sensible Daten: " + ", ".join(sorted(set(hits)))))
            continue
        rel = f"{target_rel}/{_safe_name(name)}.md"
        dest = vault._safe_path(rel)
        if dest.exists():
            out["vorhanden"].append(dest.name)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "x", encoding="utf-8") as fh:     # "x": scheitert, statt zu überschreiben
            fh.write(text)
        out["neu"].append(dest.name)
    return out
