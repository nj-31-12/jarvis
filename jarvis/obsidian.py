"""Obsidian-Wissensbasis (ein Vault ist einfach ein Ordner mit Markdown-Dateien).

JARVIS darf ohne Freigabe NUR in die erlaubten Entwurfsordner schreiben
(Standard: 00_Inbox/JARVIS). Alles andere läuft über eine 'write_file'-Freigabe.
"""
from __future__ import annotations

import datetime as dt
import os
import secrets
import re
from pathlib import Path

VAULT_FOLDERS = [
    "00_Inbox/JARVIS",
    "01_Ziele",
    "02_Projekte",
    "03_Geschäftsideen",
    "04_Entscheidungen",
    "05_Lernen",
    "06_Content",
    "07_Recherchen",
    "08_Tagebuch",
    "90_Privat",      # alles hier ist automatisch vertraulich (nie Chat-Kontext, nie Quelle)
    "99_Vorlagen",
]


def slugify(title: str) -> str:
    title = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", title)[:80] or "Notiz"


class Vault:
    def __init__(self, root: str | Path, auto_write_dirs: list[str]):
        self.root = Path(root).resolve()
        self.auto_dirs = [(self.root / d).resolve() for d in auto_write_dirs]
        self.on_write = None   # wird vom Kern gesetzt, damit der Wissensindex neue Notizen sofort sieht

    def init(self, template_dir: str | Path | None = None) -> None:
        first_setup = not self.root.exists()
        for folder in VAULT_FOLDERS:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        # Vorlagen NUR beim allerersten Einrichten kopieren (Version 4.2). Vorher wurden von dir gelöschte
        # Vorlagen bei jedem Start stillschweigend neu angelegt. Nie überschreiben.
        if first_setup and template_dir and Path(template_dir).is_dir():
            for src in Path(template_dir).rglob("*.md"):
                dst = self.root / src.relative_to(template_dir)
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    def _safe_path(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if self.root != path and self.root not in path.parents:
            raise PermissionError("Pfad liegt außerhalb des Vaults.")
        return path

    def can_auto_write(self, rel: str) -> bool:
        path = self._safe_path(rel)
        # Entwurfsordner, die (z. B. per Verknüpfung) außerhalb des Vaults liegen, sind nie erlaubt
        dirs = [d for d in self.auto_dirs if d == self.root or self.root in d.parents]
        return any(d == path.parent or d in path.parents for d in dirs)

    def write_draft(self, title: str, body: str, tags: list[str] | None = None,
                    folder: str = "00_Inbox/JARVIS", extra_meta: dict | None = None) -> Path:
        """Erstellt eine NEUE Notiz. Bestehende Dateien werden nie verändert oder gelöscht.

        Regel (von dir bestätigt): Ohne Rückfrage nur neue Notizen in 00_Inbox/JARVIS.
        Gibt es den Dateinamen schon, wird eine neue Datei mit Zusatz " (2)", " (3)" … angelegt.
        """
        base = f"{folder}/{dt.date.today().isoformat()} {slugify(title)}"
        if not self.can_auto_write(f"{base}.md"):
            raise PermissionError(f"'{folder}' ist kein freigegebener Entwurfsordner – bitte Freigabe anfragen.")
        tag_line = ", ".join(["jarvis", "entwurf", *(tags or [])])
        extra = ""
        for key, value in (extra_meta or {}).items():
            key = re.sub(r"[^a-z0-9_]", "", str(key).lower())
            value = re.sub(r"[\r\n]+", " ", str(value)).strip()
            if key and key not in ("erstellt", "quelle", "status", "tags"):
                extra += f"{key}: {value}\n"
        front = (f"---\nerstellt: {dt.datetime.now().isoformat(timespec='minutes')}\n"
                 f"quelle: JARVIS\nstatus: entwurf\ntags: [{tag_line}]\n{extra}---\n\n")
        content = front + f"# {title}\n\n{body.strip()}\n"
        first = self._safe_path(f"{base}.md")
        first.parent.mkdir(parents=True, exist_ok=True)
        # Version 4.2: erst vollständig in eine versteckte Zwischendatei schreiben, dann in EINEM Schritt
        # unter dem endgültigen Namen anlegen (Hardlink scheitert, wenn der Name existiert → nie überschreiben).
        # Ein Absturz hinterlässt so höchstens eine versteckte Zwischendatei, nie eine halbe Notiz.
        tmp = first.parent / f".jarvis-{secrets.token_hex(6)}.tmp"
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            for n in range(1, 1000):
                path = self._safe_path(f"{base}.md" if n == 1 else f"{base} ({n}).md")
                try:
                    try:
                        os.link(str(tmp), str(path))
                    except (AttributeError, NotImplementedError, PermissionError):
                        # Dateisystem ohne Hardlinks (z. B. USB-Stick): klassisch „nur neu anlegen“
                        with path.open("x", encoding="utf-8") as out:
                            out.write(content)
                    if self.on_write:
                        self.on_write()
                    return path
                except FileExistsError:
                    continue
        finally:
            try:
                os.unlink(str(tmp))
            except OSError:
                pass
        raise PermissionError("Zu viele gleichnamige Notizen – bitte Inbox aufräumen.")

    def read(self, rel: str) -> str:
        return self._safe_path(rel).read_text(encoding="utf-8")

    def list_notes(self, folder: str) -> list[Path]:
        base = self._safe_path(folder)
        return sorted(base.glob("*.md")) if base.exists() else []

    def search(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        q = query.lower()
        hits = []
        for p in self.root.rglob("*.md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            idx = text.lower().find(q)
            if idx >= 0:
                hits.append((str(p.relative_to(self.root)), text[max(0, idx - 60): idx + 120].replace("\n", " ")))
                if len(hits) >= limit:
                    break
        return hits

    def open_goals(self) -> list[str]:
        goals = []
        for p in self.list_notes("01_Ziele"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("- [ ]"):
                    goals.append(line.strip()[5:].strip())
        return goals
