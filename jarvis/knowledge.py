"""Business-Gedächtnis (Phase 2, Schritt 4): Notizen aus data/vault finden, lesen und als Quellen nutzen.

Grundsätze
- NUR LESEN. Dieses Modul schreibt, ändert oder löscht keine Datei.
- Zugriff auf eine Notiz nur über ihre Kennung aus dem Index – nie über einen Pfad aus dem Browser.
- Nur .md-Dateien innerhalb des Vaults, keine Verknüpfungen (Symlinks), keine versteckten Ordner, max. 1 MB.
- VERTRAULICH ist eine Notiz, wenn mindestens eines zutrifft:
    1. Kopfbereich (Frontmatter) enthält  vertraulich: ja  (auch: true, yes, privat)
    2. sie liegt im Ordner 90_Privat (oder einem anderen konfigurierten privaten Ordner)
    3. sie enthält etwas, das wie Zugangsdaten aussieht (Passwort:, API-Schlüssel, IBAN …)
    4. sie enthält einen Begriff aus knowledge.confidential_terms (z. B. Name des Ausbildungsbetriebs)
  Vertrauliche Notizen erscheinen NIE als Chat-Kontext oder Chat-Quelle und nur nach erneuter
  Passworteingabe in der Wissensansicht.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

MAX_NOTE_BYTES = 1024 * 1024
MAX_NOTES = 2000
MAX_QUERY_CHARS = 200
NOTE_ID = re.compile(r"[0-9a-f]{16}")
TRUE_WORDS = {"ja", "true", "yes", "1", "privat", "vertraulich"}

# Muster, die auf Zugangsdaten oder Bankdaten hindeuten → Notiz wird automatisch vertraulich
SENSITIVE_PATTERNS = [
    ("Zugangsdaten", re.compile(r"(?i)\b(passwort|password|kennwort|passcode|pin|api[ _-]?key|api[ _-]?schl[üu]ssel|"
                                r"secret|token|zugangsdaten|login)\s*[:=]\s*\S+")),
    ("API-Schlüssel", re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")),
    ("Kartennummer", re.compile(r"\b(?:\d[ -]?){15,16}\b")),
]


@dataclass
class Note:
    id: str
    relpath: str
    title: str
    folder: str
    mtime: float
    size: int
    text: str
    meta: dict = field(default_factory=dict)
    confidential: bool = False
    reasons: list = field(default_factory=list)

    @property
    def body(self) -> str:
        return split_frontmatter(self.text)[1]


def note_id_for(relpath: str) -> str:
    return hashlib.sha256(relpath.encode("utf-8")).hexdigest()[:16]


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, text[end + 4:].lstrip("\n")


def normalize(text: str) -> str:
    """Kleinschreibung, Unicode vereinheitlicht (ä bleibt ä, aber gleiche Darstellung)."""
    return unicodedata.normalize("NFC", text).lower()


# Häufige Füllwörter: zählen bei der Suche nicht (sonst findet eine Frage wie „Wie nutze ich …?“ nichts)
STOPWORDS = set("""
der die das den dem des ein eine einen einem einer eines und oder aber auch als am an auf aus bei bin bis bist
da dann dass dazu dein deine dem den denn der des dich dir du durch er es etwas für gegen hab habe haben hat
hier ich ihr im in ins ist ja jetzt kann kannst können mal man mehr mein meine meinen meinem meiner mich mir
mit muss müssen nach nicht noch nur ob oder ohne schon sein sich sie sind so soll sollte über um und uns unser
unsere vom von vor war was weil welche welcher welches wenn wer werden wie wieso wird wir wo zu zum zur zwischen
bitte gibt geht gut viel sehr nutze nutzen machen mache macht
""".split())


def tokens(text: str, keep_stopwords: bool = False) -> list[str]:
    words = [t for t in re.findall(r"[0-9a-zäöüß]+", normalize(text)) if len(t) >= 2]
    if keep_stopwords:
        return words
    filtered = [t for t in words if t not in STOPWORDS]
    return filtered or words      # nur Füllwörter? Dann doch danach suchen


def plain_text(markdown: str) -> str:
    """Markdown → lesbarer Fließtext für Suchausschnitte und Kontext (keine Tabellenstriche, keine ##)."""
    text = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    text = re.sub(r"^\s*\|?[\s:\-|]+\|?\s*$", " ", text, flags=re.M)        # Tabellen-Trennzeilen
    text = re.sub(r"^\s{0,3}(#{1,6}|>+|[-*+]\s+\[[ xX]\]|[-*+]|\d+[.)])\s*", "", text, flags=re.M)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)                  # Links/Bilder → Text
    text = re.sub(r"\[\[([^\]|]+)\|?([^\]]*)\]\]", lambda m: m.group(2) or m.group(1), text)
    text = text.replace("|", " · ")
    text = text.replace("`", "")
    text = re.sub(r"(?<![0-9A-Za-zÄÖÜäöüß])[*_]{1,3}|[*_]{1,3}(?![0-9A-Za-zÄÖÜäöüß])", "", text)   # nur Formatierung, nicht 02_Projekte
    text = re.sub(r"(\s·\s*){2,}", " · ", text)
    return re.sub(r"\s+", " ", text).strip(" ·")


def quote_fingerprints(text: str, limit: int = 60) -> list[str]:
    """Prüfmerkmale (gekürzte SHA-256) der zitierten Zeilen. Enthält KEINEN Klartext.

    Damit lässt sich später prüfen, ob genau diese Inhalte noch in einer nicht vertraulichen Notiz stehen –
    unabhängig davon, ob die Notiz verschoben, umbenannt oder durch eine andere gleichen Namens ersetzt wurde.
    """
    out = []
    for line in plain_text_lines(text):
        h = hashlib.sha256(line.encode("utf-8")).hexdigest()[:20]
        if h not in out:
            out.append(h)
        if len(out) >= limit:
            break
    return out


def plain_text_lines(text: str) -> list[str]:
    """Normalisierte, aussagekräftige Zeilen (ohne Formatierung, ohne Leer- und Trennzeilen)."""
    lines = []
    for raw in split_frontmatter(text)[1].splitlines():
        line = normalize(plain_text(raw)).strip(" .…")
        if len(line) >= 3:
            lines.append(line)
    return lines


class KnowledgeBase:
    def __init__(self, vault_root: str | Path, private_dirs: list[str] | None = None,
                 confidential_terms: list[str] | None = None, max_note_bytes: int = MAX_NOTE_BYTES,
                 max_notes: int = MAX_NOTES, min_interval: float = 2.0):
        self.root = Path(vault_root).resolve()
        self.private_dirs = [d.strip("/").lower() for d in (private_dirs if private_dirs is not None else ["90_Privat"])]
        self.terms = [t.strip().lower() for t in (confidential_terms or []) if t.strip()
                      and not t.strip().upper().startswith("NAME_DEINES")]   # Platzhalter ignorieren
        self.max_bytes = max_note_bytes
        self.max_notes = max_notes
        self._lock = threading.Lock()
        self._notes: dict[str, Note] = {}
        self._signature = None
        self._checked_at = 0.0
        self.min_interval = min_interval     # höchstens alle 2 s auf Änderungen prüfen (schont den alten Mac)
        self.skipped = {"zu_gross": 0, "verknuepfung": 0, "zu_viele": 0, "unlesbar": 0}

    # ------------------------------------------------------------------ Index
    def _walk(self):
        """Alle .md-Dateien im Vault – ohne Symlinks, ohne versteckte Ordner, nur innerhalb des Vaults."""
        if not self.root.is_dir():
            return
        for dirpath, dirnames, filenames in os.walk(str(self.root), followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".")
                                 and not os.path.islink(os.path.join(dirpath, d)))
            for name in sorted(filenames):
                if name.startswith(".") or not name.lower().endswith(".md"):
                    continue
                yield Path(dirpath) / name

    def _current_signature(self):
        sig = []
        for p in self._walk():
            try:
                st = os.lstat(str(p))
            except OSError:
                continue
            sig.append((str(p), st.st_mtime, st.st_size))
        return tuple(sig)

    def invalidate(self) -> None:
        """Beim nächsten Zugriff sofort neu prüfen (z. B. nachdem JARVIS eine Notiz angelegt hat)."""
        self._checked_at = 0.0

    def refresh(self, force: bool = False) -> None:
        """Index neu aufbauen, wenn sich etwas geändert hat (schonend für den alten Mac)."""
        with self._lock:
            now = time.monotonic()
            if not force and self._signature is not None and now - self._checked_at < self.min_interval:
                return
            self._checked_at = now
            sig = self._current_signature()
            if not force and sig == self._signature:
                return
            notes, skipped = {}, {"zu_gross": 0, "verknuepfung": 0, "zu_viele": 0, "unlesbar": 0}
            for path_str, mtime, size in sig:
                path = Path(path_str)
                if os.path.islink(path_str):
                    skipped["verknuepfung"] += 1
                    continue
                resolved = path.resolve()
                if self.root not in resolved.parents:
                    skipped["verknuepfung"] += 1
                    continue
                if size > self.max_bytes:
                    skipped["zu_gross"] += 1
                    continue
                if len(notes) >= self.max_notes:
                    skipped["zu_viele"] += 1
                    continue
                try:
                    text = resolved.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    skipped["unlesbar"] += 1
                    continue
                rel = resolved.relative_to(self.root).as_posix()
                note = self._make_note(rel, text, mtime, size)
                notes[note.id] = note
            self._notes, self._signature, self.skipped = notes, sig, skipped

    def _make_note(self, rel: str, text: str, mtime: float, size: int) -> Note:
        meta, body = split_frontmatter(text)
        m = re.search(r"^#\s+(.+)$", body, flags=re.M)
        title = (m.group(1).strip() if m else Path(rel).stem)[:200]
        folder = rel.split("/", 1)[0] if "/" in rel else ""
        reasons = self._confidential_reasons(rel, meta, text)
        return Note(id=note_id_for(rel), relpath=rel, title=title, folder=folder, mtime=mtime, size=size,
                    text=text, meta=meta, confidential=bool(reasons), reasons=reasons)

    def _confidential_reasons(self, rel: str, meta: dict, text: str) -> list[str]:
        reasons = []
        if normalize(meta.get("vertraulich", "") or meta.get("privat", "")) in TRUE_WORDS:
            reasons.append("als vertraulich markiert")
        low_rel = rel.lower()
        if any(low_rel == d or low_rel.startswith(d + "/") for d in self.private_dirs):
            reasons.append("privater Ordner")
        for label, pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                reasons.append(f"enthält möglicherweise {label}")
        low = normalize(text)
        if any(t in low for t in self.terms):
            reasons.append("enthält einen geschützten Begriff")
        return reasons

    def _fresh(self, note: Note) -> Note | None:
        """Liest die Datei JETZT neu und bewertet die Vertraulichkeit erneut.

        Schließt die Lücke zwischen Dateiänderung und nächstem Index-Neuaufbau (bis zu 2 s):
        Der Index dient nur zum Finden – ob eine Notiz verwendet werden darf, entscheidet immer
        der aktuelle Dateiinhalt. Gibt None zurück, wenn die Datei fehlt, verschoben wurde,
        zur Verknüpfung wurde, zu groß ist oder außerhalb des Vaults liegt.
        """
        path_str = str(self.root / note.relpath)
        try:
            if os.path.islink(path_str):
                return None
            st = os.lstat(path_str)
            resolved = Path(path_str).resolve()
            if self.root not in resolved.parents or st.st_size > self.max_bytes:
                return None
            text = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        fresh = self._make_note(note.relpath, text, st.st_mtime, st.st_size)
        if fresh.confidential != note.confidential or fresh.mtime != note.mtime:
            self.invalidate()        # Index beim nächsten Zugriff aktualisieren
        return fresh

    def _usable(self, note: Note) -> Note | None:
        """Aktueller Stand der Notiz, aber nur wenn sie JETZT nicht vertraulich ist."""
        if note.confidential:
            return None
        fresh = self._fresh(note)
        return fresh if fresh is not None and not fresh.confidential else None

    # ------------------------------------------------------------------ Abfragen
    def notes(self, include_confidential: bool = False) -> list[Note]:
        self.refresh()
        with self._lock:
            items = list(self._notes.values())
        return [n for n in items if include_confidential or not n.confidential]

    def get(self, note_id: str | None, include_confidential: bool = False) -> Note | None:
        if not note_id or NOTE_ID.fullmatch(note_id) is None:
            return None
        self.refresh()
        with self._lock:
            note = self._notes.get(note_id)
        if note is None:
            self.refresh(force=True)          # evtl. gerade neu angelegt: Index sofort aktualisieren
            with self._lock:
                note = self._notes.get(note_id)
        if note is None:
            return None
        # Version 4.2: Entscheidung IMMER auf dem aktuellen Dateistand, nie auf dem Zwischenspeicher
        fresh = self._fresh(note)
        if fresh is None or (fresh.confidential and not include_confidential):
            return None
        return fresh

    def stats(self) -> dict:
        self.refresh()
        with self._lock:
            items = list(self._notes.values())
        folders: dict[str, int] = {}
        for n in items:
            if not n.confidential:
                folders[n.folder or "(Hauptordner)"] = folders.get(n.folder or "(Hauptordner)", 0) + 1
        return {"total": len(items), "visible": sum(1 for n in items if not n.confidential),
                "confidential": sum(1 for n in items if n.confidential), "folders": dict(sorted(folders.items())),
                "skipped": dict(self.skipped)}

    def search(self, query: str, include_confidential: bool = False, limit: int = 20,
               min_share: float = 1.0) -> list[dict]:
        """Stichwortsuche ohne Füllwörter. Treffer im Titel zählen dreifach.

        min_share=1.0: alle Suchwörter müssen vorkommen (Suchfeld).
        min_share=0.5: mindestens die Hälfte (Chat-Fragen in natürlicher Sprache).
        """
        terms = list(dict.fromkeys(tokens((query or "")[:MAX_QUERY_CHARS])))[:12]
        if not terms:
            return []
        needed = max(1, -(-int(len(terms) * min_share * 100) // 100))   # aufrunden
        hits = []
        for n in self.notes(include_confidential):
            title_t, body_n = normalize(n.title), normalize(n.body)
            score, matched = 0, 0
            for t in terms:
                in_title, in_body = title_t.count(t), body_n.count(t)
                if in_title or in_body:
                    matched += 1
                    score += 3 * in_title + min(in_body, 20)
            if matched >= needed and score:
                score *= matched          # mehr passende Wörter = deutlich relevanter
                if n.relpath.startswith("00_Inbox/"):
                    score = score * 0.5          # ungeprüfte Entwürfe zählen halb (Kommazahl: auch bei 1 Punkt wirksam)
                hits.append({"note": n, "score": score, "snippet": self._snippet(n.body, terms)})
        hits.sort(key=lambda h: (-h["score"], -h["note"].mtime))
        hits = hits[:max(1, min(int(limit), 50))]
        if include_confidential:
            return hits
        checked = []
        for h in hits:              # nur ausliefern, was JETZT noch nicht vertraulich ist
            fresh = self._usable(h["note"])
            if fresh is not None:
                checked.append({"note": fresh, "score": h["score"], "snippet": self._snippet(fresh.body, terms)})
        return checked

    @staticmethod
    def _snippet(body: str, terms: list[str], width: int = 180) -> str:
        flat = plain_text(body)
        low = normalize(flat)
        pos = min([p for p in (low.find(t) for t in terms) if p >= 0] or [0])
        start = max(0, pos - width // 3)
        return ("…" if start else "") + flat[start:start + width].strip() + ("…" if start + width < len(flat) else "")

    def context_for(self, query: str, k: int = 3, max_chars: int = 1200) -> list[dict]:
        """Kontext für das Sprachmodell. Vertrauliche Notizen sind hier IMMER ausgeschlossen (kein Schalter)."""
        result = []
        for hit in self.search(query, include_confidential=False, limit=k, min_share=0.5):
            note = self._usable(hit["note"])   # unmittelbar vor der Verwendung erneut von der Festplatte prüfen
            if note is None:
                continue
            excerpt = note.body.strip()
            if len(excerpt) > max_chars:
                excerpt = excerpt[:max_chars].rsplit("\n", 1)[0] + "\n…"
            result.append({"id": note.id, "title": note.title, "relpath": note.relpath, "excerpt": excerpt})
        return result

    def recent(self, limit: int = 10, include_confidential: bool = False) -> list[Note]:
        """Zuletzt geänderte Notizen – jede einzelne auf dem aktuellen Dateistand geprüft (keine Titel aus
        dem Zwischenspeicher für inzwischen vertrauliche Notizen)."""
        out = []
        for n in sorted(self.notes(include_confidential=True), key=lambda x: -x.mtime):
            fresh = self._fresh(n)
            if fresh is None or (fresh.confidential and not include_confidential):
                continue
            out.append(fresh)
            if len(out) >= limit:
                break
        return out

    def quotes_still_shareable(self, note_id: str, fingerprints) -> bool:
        """Darf eine gespeicherte Antwort mit dieser Quelle gezeigt bzw. an ein Modell gegeben werden?

        Nur wenn die ursprüngliche Quelle JETZT nicht vertraulich ist UND alle damals zitierten Zeilen
        (Prüfmerkmale) noch darin stehen. Verschoben, umbenannt, gelöscht oder durch eine andere Notiz
        gleichen Namens ersetzt → False (vorsorglich zurückhalten). fingerprints=None bedeutet: Antwort aus
        einer älteren Version ohne Prüfmerkmale → ebenfalls vorsorglich False.
        """
        if fingerprints is None:
            return False
        note = self.get(note_id)                 # frisch gelesen, None wenn vertraulich/fehlend
        if note is None:
            return False
        wanted = set(fingerprints)
        if not wanted:
            return True                           # es wurde nichts zitiert
        return wanted <= set(quote_fingerprints(note.text, limit=100000))

    def is_shareable(self, note_id: str) -> bool:
        """Darf diese Notiz (noch) als Quelle gezeigt werden? Prüft den AKTUELLEN Stand."""
        return self.get(note_id, include_confidential=False) is not None

    def open_checkboxes(self, limit: int = 50) -> list:
        """Version 5: offene Aufgaben „- [ ]“ aus allen NICHT vertraulichen Notizen (frischer Dateistand)."""
        out = []
        for n in self.notes(include_confidential=False):
            fresh = self._usable(n)
            if fresh is None:
                continue
            for line in fresh.body.splitlines():
                if line.strip().startswith("- [ ]"):
                    out.append((fresh.title, line.strip()[5:].strip()[:200]))
                    if len(out) >= limit:
                        return out
        return out

    def open_goals(self) -> list[str]:
        goals = []
        for n in self.notes(include_confidential=False):
            if n.folder != "01_Ziele":
                continue
            fresh = self._usable(n)
            if fresh is not None:
                goals += [line.strip()[5:].strip() for line in fresh.body.splitlines() if line.strip().startswith("- [ ]")]
        return goals
