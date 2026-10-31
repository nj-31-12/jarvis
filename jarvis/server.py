"""Betrieb auf einem eigenen Server (Version 5, Phase D) – alles funktioniert auch schon auf dem Mac.

Enthalten:
  - instance_lock: verhindert, dass derselbe Dienst zweimal gleichzeitig läuft (doppelte Ausführung).
  - preflight: Prüfungen vor dem Start. Im Modus "server" führen Fehler zum Abbruch.
  - health_report: Gesundheitsprüfung (nur lesen) mit Rückgabewert für Überwachung/systemd.
  - make_backup / restore_backup: konsistente Sicherung als .tar.gz mit Prüfsummen; Wiederherstellung NUR in
    einen leeren Ordner – bestehende Daten werden nie überschrieben.

Bewusst NICHT enthalten: Verbindung ins Internet. JARVIS lauscht weiterhin nur auf 127.0.0.1. Der Zugang von
außen erfolgt später ausschließlich über einen privaten, verschlüsselten Tunnel (siehe docs/19).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import tarfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover – Windows
    fcntl = None

BACKUP_PREFIX = "jarvis-sicherung-"
MANIFEST = "MANIFEST.json"
SKIP_SUFFIXES = ("-wal", "-shm", "-journal")
# Version 5.3: Geheimnisse kommen NIE in eine Sicherung. Nach einer Wiederherstellung entsteht ein neues
# Freigabe-Geheimnis automatisch; das Browser-Passwort wird mit `python3 -m jarvis web-passwort` neu gesetzt.
SECRET_FILES = frozenset({".approval_secret", "web_auth.json"})
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class AlreadyRunning(RuntimeError):
    pass


class BackupError(RuntimeError):
    pass


# ---------------------------------------------------------------------- Nur eine Instanz je Dienst
@contextlib.contextmanager
def instance_lock(data_dir, role: str):
    """Sperre data/.lock-<role>. Ein zweiter Start desselben Dienstes bricht mit klarer Meldung ab.
    Die Sperre löst sich automatisch, wenn der Prozess endet (auch nach einem Absturz)."""
    path = Path(data_dir) / f".lock-{role}"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise AlreadyRunning(f"JARVIS ({role}) läuft bereits. Ein zweiter Start würde Aufgaben doppelt "
                                     f"ausführen und wurde verhindert.") from None
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        yield path
    finally:
        if fcntl is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# ---------------------------------------------------------------------- Prüfungen
def _readable_by_others(p: Path) -> bool:
    return p.exists() and bool(p.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH))


def preflight(cfg: dict, env_file: Path | None = None) -> list:
    """Prüfungen vor dem Start. Gibt (Stufe, Text) zurück. Im Server-Modus gelten Warnungen zu Rechten als Fehler."""
    from .config import PROJECT_ROOT
    server = cfg.get("server", {}).get("mode") == "server"
    strict = "fehler" if server else "warnung"
    out = []
    data = Path(cfg["data_dir"])
    if cfg.get("web", {}).get("host") not in LOCAL_HOSTS:
        out.append(("fehler", "web.host ist nicht 127.0.0.1 – JARVIS darf nie direkt öffentlich erreichbar sein."))
    env = Path(env_file) if env_file else Path(os.environ.get("JARVIS_ENV_FILE") or PROJECT_ROOT / ".env")
    if _readable_by_others(env):
        out.append(("fehler", f"{env.name} ist für andere Benutzer lesbar → chmod 600 {env}"))
    for name in ("web_auth.json", ".approval_secret"):
        if _readable_by_others(data / name):
            out.append(("fehler", f"data/{name} ist für andere lesbar → chmod 600"))
    if data.exists() and data.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        out.append((strict, f"Datenordner ist für andere Benutzer zugänglich → chmod 700 {data}"))
    if server:
        if cfg.get("web", {}).get("approvals_enabled") and not cfg.get("web", {}).get("users"):
            out.append(("warnung", "Server-Modus: Bitte web.users ausdrücklich setzen (nur dein Benutzername)."))
        if cfg.get("privacy", {}).get("external_ai_allowed"):
            out.append(("warnung", "Server-Modus: Externe KI ist erlaubt. Prüfe, ob das gewollt ist."))
    if not out:
        out.append(("ok", "Startprüfung bestanden."))
    return out


def jarvis_running(data_dir) -> bool:
    """Läuft gerade ein JARVIS-Dienst (Web oder Aufgabenplaner) auf diesem Datenordner?

    Version 5.2: Erkannt an den Sperrdateien, NICHT an einer -wal-Datei. Auf macOS lässt das mitgelieferte SQLite
    -wal und -shm nach dem Schließen stehen („persistentes WAL“) – daraus folgt nicht, dass JARVIS läuft.
    Die Sperrdatei wird nur zum Lesen geöffnet und kurz geprüft; sie wird nicht verändert oder angelegt."""
    if fcntl is None:
        return False
    for role in ("web", "aufgaben"):
        lock = Path(data_dir) / f".lock-{role}"
        if not lock.is_file():
            continue
        fd = os.open(str(lock), os.O_RDONLY)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except OSError:
                return True                      # ein anderer Prozess hält die Sperre
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    return False


def _stat_key(path: Path) -> tuple:
    try:
        st = path.stat()
        return st.st_size, st.st_mtime_ns
    except FileNotFoundError:
        return None


@contextlib.contextmanager
def _readable_copy(path: Path):
    """Liefert eine Verbindung zum Lesen, OHNE den Datenordner zu verändern.

    Läuft JARVIS nicht: Datenbank und ggf. -wal werden in einen temporären Ordner kopiert und DORT geöffnet.
    SQLite darf dort seine Hilfsdateien anlegen und ein -wal einarbeiten; das Original bleibt Byte für Byte gleich,
    und noch nicht übernommene Einträge aus dem -wal gehen nicht verloren.
    Ändert sich die Datei während des Kopierens (anderer Prozess schreibt), wird bis zu dreimal wiederholt.
    Läuft JARVIS (Sperre gehalten): normal lesend öffnen – dann pflegt JARVIS die Hilfsdateien ohnehin selbst."""
    import tempfile
    wal = path.with_name(path.name + "-wal")
    if not jarvis_running(path.parent):
        for _ in range(3):
            before = (_stat_key(path), _stat_key(wal))
            with tempfile.TemporaryDirectory(prefix="jarvis-pruefung-") as d:
                copy = Path(d) / path.name
                shutil.copyfile(str(path), str(copy))
                if wal.is_file() and wal.stat().st_size > 0:
                    shutil.copyfile(str(wal), str(copy) + "-wal")
                if (_stat_key(path), _stat_key(wal)) != before:
                    continue                     # während des Kopierens verändert → noch einmal
                con = sqlite3.connect(str(copy), timeout=5)
                try:
                    yield con
                finally:
                    con.close()
                return
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    try:
        yield con
    finally:
        con.close()


def _db_ok(path: Path) -> tuple:
    try:
        with _readable_copy(path) as con:
            res = con.execute("PRAGMA quick_check").fetchone()[0]
        return res == "ok", res
    except (sqlite3.Error, OSError) as exc:
        return False, str(exc)


def health_report(cfg: dict, now: float | None = None) -> list:
    """NUR LESEN. (Stufe, Bereich, Text). Stufen: ok · warnung · fehler."""
    from .audit import AuditLog
    now = time.time() if now is None else now
    out = []
    data = Path(cfg["data_dir"])
    if not data.is_dir():
        return [("fehler", "Daten", f"Datenordner fehlt: {data}")]
    # Version 5.2: Beschreibbarkeit nur ABFRAGEN (früher: Testdatei anlegen und löschen → Ordner verändert)
    if os.access(str(data), os.W_OK | os.X_OK):
        out.append(("ok", "Daten", "Datenordner beschreibbar."))
    else:
        out.append(("fehler", "Daten", "Datenordner nicht beschreibbar (Rechte prüfen)."))
    free_mb = shutil.disk_usage(str(data)).free // (1024 * 1024)
    need = int(cfg.get("server", {}).get("min_free_mb", 500))
    out.append(("ok" if free_mb >= need else "fehler", "Speicher", f"{free_mb} MB frei (Minimum {need} MB)."))
    for db in sorted(data.glob("*.db")):
        ok, msg = _db_ok(db)
        out.append(("ok" if ok else "fehler", "Datenbank", f"{db.name}: {'in Ordnung' if ok else msg}"))
    ok, msg = AuditLog(data / "audit.jsonl").verify()
    out.append(("ok" if ok else "fehler", "Protokoll", msg))
    out.append(("warnung" if (data / "KILL").exists() else "ok", "Notaus",
                "Notabschaltung AKTIV." if (data / "KILL").exists() else "Notabschaltung aus."))
    latest = latest_backup(cfg)
    max_h = float(cfg.get("server", {}).get("backup_max_age_hours", 48))
    if latest is None:
        out.append(("warnung", "Sicherung", "Noch keine Sicherung vorhanden → python3 -m jarvis sicherung"))
    else:
        age_h = (now - latest.stat().st_mtime) / 3600
        out.append(("ok" if age_h <= max_h else "warnung", "Sicherung",
                    f"Letzte Sicherung vor {age_h:.0f} Std. ({latest.name})."))
    for level, text in preflight(cfg):
        if level != "ok":
            out.append((level, "Sicherheit", text))
    return out


def health_exit_code(report: list) -> int:
    levels = {lvl for lvl, _, _ in report}
    return 2 if "fehler" in levels else (1 if "warnung" in levels else 0)


# ---------------------------------------------------------------------- Umstellung älterer Daten
def _has_table(db: Path, table: str) -> bool:
    with _readable_copy(db) as con:
        return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def pending_upgrades(cfg: dict) -> list:
    """NUR LESEN: Welche bestehenden Dateien würde Version 5 beim Start ergänzen? Leere Liste = nichts."""
    from .chat import pending_migration
    data = Path(cfg["data_dir"])
    out = []
    missing = pending_migration(data / "chat.db")
    if missing:
        out.append(f"data/chat.db: Spalten {', '.join(missing)} ergänzen (Quellenangaben). Der Verlauf bleibt vollständig.")
    actions = data / "actions.db"
    if actions.exists() and not _has_table(actions, "action_meta"):
        out.append("data/actions.db: neue Tabelle action_meta (Beschreibung, Konten, Daten, Kosten je Aktion). "
                   "Bestehende Aktionen bleiben unverändert.")
    return out


def apply_upgrades(cfg: dict) -> None:
    """Version 5.3: Nach Noahs „ja“ und der Sicherung die Ergänzungen SOFORT anlegen. Vorher entstand action_meta
    erst bei der ersten Freigabe – bis dahin fragte jeder Start erneut. Nur ergänzen, nie löschen oder ändern."""
    actions = Path(cfg["data_dir"]) / "actions.db"
    if actions.exists() and not _has_table(actions, "action_meta"):
        con = sqlite3.connect(str(actions))
        try:
            con.execute("CREATE TABLE IF NOT EXISTS action_meta (id TEXT PRIMARY KEY, meta TEXT, replaces TEXT)")
            con.commit()
        finally:
            con.close()


# ---------------------------------------------------------------------- Sicherung
def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def latest_backup(cfg: dict) -> Path | None:
    folder = Path(cfg["backup"]["dir"])
    found = sorted(folder.glob(f"{BACKUP_PREFIX}*.tar.gz")) if folder.is_dir() else []
    return found[-1] if found else None


def make_backup(cfg: dict, target_dir: str | Path | None = None, clock=time.time, limits=None) -> Path:
    """Konsistente Sicherung des ganzen Datenordners. Datenbanken über die SQLite-Sicherungsschnittstelle (auch bei
    laufendem JARVIS sicher). Legt immer eine NEUE Datei an, überschreibt und löscht nichts."""
    data = Path(cfg["data_dir"]).resolve()
    if not data.is_dir():
        raise BackupError(f"Datenordner fehlt: {data}")
    target = Path(target_dir or cfg["backup"]["dir"]).expanduser().resolve()
    if target == data or data in target.parents:
        raise BackupError("Der Sicherungsordner darf nicht im Datenordner liegen.")
    target.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(str(target), 0o700)
    stamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime(clock()))
    archive = target / f"{BACKUP_PREFIX}{stamp}.tar.gz"
    n = 1
    while archive.exists():
        archive = target / f"{BACKUP_PREFIX}{stamp}-{n}.tar.gz"
        n += 1
    limits = limits or LIMITS
    files, total = [], 0
    tmp = archive.with_name(archive.name + ".teil")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as tar:
            for path in sorted(data.rglob("*")):
                rel = path.relative_to(data).as_posix()
                if path.is_symlink() or not path.is_file() or rel.endswith(SKIP_SUFFIXES) or \
                        rel.startswith(".lock-") or rel.startswith(".gesundheit-") or rel in SECRET_FILES:
                    continue
                if not valid_backup_path(rel):
                    raise BackupError(f"Dateiname nicht sicherbar (Steuerzeichen oder Backslash): {rel[:80]!r}. "
                                      f"Bitte die Datei umbenennen.")
                if len(files) + 1 >= limits.entries or path.stat().st_size > limits.file_bytes:
                    raise BackupError(f"Sicherung überschreitet die Grenzen (Datei {rel[:80]!r} oder Anzahl).")
                content = _sqlite_snapshot(path) if path.suffix == ".db" else path.read_bytes()
                total += len(content)
                if len(content) > limits.file_bytes or total > limits.total_bytes:
                    raise BackupError("Sicherung überschreitet die Größengrenzen. Bitte melden.")
                files.append({"pfad": rel, "bytes": len(content), "sha256": _sha256(content)})
                _add(tar, "data/" + rel, content)
            manifest = {"erstellt": stamp, "version": _version(), "dateien": files,
                        "hinweis": "Ohne Passwort und Freigabe-Geheimnis (seit 5.3). Nach dem Wiederherstellen: python3 -m jarvis web-passwort. Enthält trotzdem persönliche Daten – nicht hochladen."}
            _add(tar, MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            raw.flush()
            os.fsync(raw.fileno())
        os.link(str(tmp), str(archive))       # schlägt fehl, falls es die Datei inzwischen gibt → nie überschreiben
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
    return archive


def _sqlite_snapshot(path: Path) -> bytes:
    """Konsistente Kopie einer Datenbank über die SQLite-Sicherungsschnittstelle – ohne den Datenordner zu
    verändern (Version 5.2, siehe _readable_copy). Die Kopie wird vor dem Einpacken auf Fehler geprüft."""
    import tempfile
    with _readable_copy(path) as src, tempfile.TemporaryDirectory() as d:
        out = Path(d) / "kopie.db"
        dest = sqlite3.connect(str(out))
        try:
            src.backup(dest)
            ok = dest.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            dest.execute("PRAGMA journal_mode=DELETE")       # Kopie als einzelne, in sich vollständige Datei
        finally:
            dest.close()
        if not ok:
            raise BackupError(f"{path.name} konnte nicht konsistent gelesen werden. Bitte die Sicherung wiederholen.")
        return out.read_bytes()


def _add(tar: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = 0o600
    info.mtime = int(time.time())
    tar.addfile(info, io.BytesIO(content))


def _version() -> str:
    from . import __version__
    return __version__


# Version 5.1: Grenzen für Sicherungsarchive (Schutz vor beschädigten oder böswilligen Archiven, „Zip-Bomben“)
@dataclass(frozen=True)
class BackupLimits:
    archive_bytes: int = 2 * 1024 ** 3        # Archiv (komprimiert) höchstens 2 GiB
    total_bytes: int = 8 * 1024 ** 3          # alle Dateien zusammen (entpackt) höchstens 8 GiB
    file_bytes: int = 2 * 1024 ** 3           # eine einzelne Datei höchstens 2 GiB
    entries: int = 50_000                     # höchstens so viele Einträge
    manifest_bytes: int = 16 * 1024 ** 2      # MANIFEST.json höchstens 16 MiB


LIMITS = BackupLimits()
CHUNK = 1024 * 1024
SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def valid_backup_path(rel) -> bool:
    """Relativer Pfad innerhalb des Datenordners, ohne jeden Trick: kein absoluter Pfad, kein „..“ oder „.“, keine
    leeren Teile („a//b“), kein Backslash, keine Steuerzeichen, Teile höchstens 255 Byte."""
    if not isinstance(rel, str) or not 0 < len(rel) <= 1024 or rel.startswith("/") or "\\" in rel:
        return False
    if any(unicodedata.category(ch)[0] == "C" for ch in rel):       # auch NUL, Zeilenumbruch, Tab
        return False
    parts = rel.split("/")
    return all(part not in ("", ".", "..") and len(part.encode("utf-8")) <= 255 for part in parts)


def _scan_members(tar: tarfile.TarFile, limits: BackupLimits) -> dict:
    """Liest alle Einträge EINMAL und prüft dabei sofort: Anzahl, Typ, Name, Doppelungen, Größen."""
    members, total = {}, 0
    for m in tar:
        if len(members) >= limits.entries:
            raise BackupError(f"Zu viele Einträge im Archiv (höchstens {limits.entries}).")
        name = m.name
        if name != MANIFEST and not (name.startswith("data/") and valid_backup_path(name[5:])):
            raise BackupError(f"Unerlaubter Name im Archiv: {name[:80]!r}")
        if not m.isreg():
            raise BackupError(f"Unerlaubter Eintragstyp (nur normale Dateien): {name[:80]!r}")
        if name in members:
            raise BackupError(f"Doppelter Eintrag im Archiv: {name[:80]!r}")
        limit = limits.manifest_bytes if name == MANIFEST else limits.file_bytes
        if m.size > limit:
            raise BackupError(f"Datei zu groß im Archiv: {name[:80]!r}")
        total += m.size
        if total > limits.total_bytes:
            raise BackupError("Entpackte Gesamtgröße überschreitet die Grenze.")
        members[name] = m
    return members


def _read_manifest(tar: tarfile.TarFile, members: dict) -> dict:
    if MANIFEST not in members:
        raise BackupError("Archiv ohne MANIFEST.json – keine JARVIS-Sicherung.")
    try:
        manifest = json.loads(tar.extractfile(members[MANIFEST]).read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise BackupError("MANIFEST.json ist kein gültiges JSON.") from None
    files = manifest.get("dateien") if isinstance(manifest, dict) else None
    if not isinstance(files, list):
        raise BackupError("MANIFEST.json hat keine Dateiliste.")
    seen = set()
    for f in files:
        if not isinstance(f, dict):
            raise BackupError("Ungültiger Eintrag in MANIFEST.json.")
        rel, size, digest = f.get("pfad"), f.get("bytes"), f.get("sha256")
        if not valid_backup_path(rel):
            raise BackupError(f"Unerlaubter Pfad in MANIFEST.json: {str(rel)[:80]!r}")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise BackupError(f"Ungültige Größe in MANIFEST.json: {rel[:80]!r}")
        if not isinstance(digest, str) or not SHA256_HEX.fullmatch(digest):
            raise BackupError(f"Ungültige Prüfsumme in MANIFEST.json: {rel[:80]!r}")
        if rel in seen:
            raise BackupError(f"Doppelter Pfad in MANIFEST.json: {rel[:80]!r}")
        seen.add(rel)
    return manifest


def _check_against_manifest(members: dict, manifest: dict) -> None:
    expected = {"data/" + f["pfad"] for f in manifest["dateien"]}
    present = set(members) - {MANIFEST}
    if expected != present:
        raise BackupError("Archiv und Manifest stimmen nicht überein (fehlende oder zusätzliche Dateien).")
    for f in manifest["dateien"]:
        if members["data/" + f["pfad"]].size != f["bytes"]:
            raise BackupError(f"Größe stimmt nicht mit dem Manifest überein: {f['pfad'][:80]!r}")


def _copy_hashed(src, dest_fh, expected_size: int) -> str:
    """Kopiert in Blöcken (nie die ganze Datei im Speicher) und liefert die SHA-256-Prüfsumme."""
    h, n = hashlib.sha256(), 0
    while True:
        chunk = src.read(CHUNK)
        if not chunk:
            break
        n += len(chunk)
        if n > expected_size:
            raise BackupError("Datei ist größer als im Manifest angegeben.")
        h.update(chunk)
        if dest_fh is not None:
            dest_fh.write(chunk)
    if n != expected_size:
        raise BackupError("Datei ist kleiner als im Manifest angegeben.")
    return h.hexdigest()


def _open_archive(archive: Path, limits: BackupLimits) -> tarfile.TarFile:
    if archive.is_symlink() or not archive.is_file():
        raise BackupError("Sicherung nicht gefunden oder keine normale Datei.")
    if archive.stat().st_size > limits.archive_bytes:
        raise BackupError("Sicherungsarchiv ist größer als erlaubt.")
    return tarfile.open(str(archive), "r:gz")


def verify_backup(archive: str | Path, limits: BackupLimits = LIMITS) -> dict:
    """Prüft ein Archiv vollständig (nur lesen). Gibt das Manifest zurück oder löst BackupError aus."""
    archive = Path(archive)
    try:
        with _open_archive(archive, limits) as tar:
            members = _scan_members(tar, limits)
            manifest = _read_manifest(tar, members)
            _check_against_manifest(members, manifest)
            for f in manifest["dateien"]:
                if _copy_hashed(tar.extractfile(members["data/" + f["pfad"]]), None, f["bytes"]) != f["sha256"]:
                    raise BackupError(f"Prüfsumme falsch: {f['pfad'][:80]!r}")
    except BackupError:
        raise
    except (tarfile.TarError, OSError, EOFError, ValueError, KeyError) as exc:
        raise BackupError(f"Sicherung ist beschädigt oder unlesbar ({exc.__class__.__name__}).") from exc
    return manifest


def restore_backup(archive: str | Path, target_dir: str | Path, limits: BackupLimits = LIMITS) -> Path:
    """Stellt eine Sicherung in einen NEUEN oder LEEREN Ordner wieder her.

    Ablauf (Version 5.1): vollständige Prüfung → Auspacken in einen versteckten Zwischenordner, dabei jede Datei
    ERNEUT gegen das Manifest prüfen (das Archiv könnte sich seit der Prüfung geändert haben) → erst wenn alles
    stimmt, in einem Schritt umbenennen. Bei jedem Fehler bleibt das Ziel unberührt; nur der eigene
    Zwischenordner wird entfernt.
    """
    import tempfile
    archive = Path(archive)
    target = Path(target_dir).expanduser().resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise BackupError(f"Zielordner {target} ist nicht leer. Es wird nichts überschrieben – bitte einen neuen "
                          f"Ordner angeben.")
    manifest = verify_backup(archive, limits)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.wiederherstellung-", dir=str(target.parent)))
    try:
        with _open_archive(archive, limits) as tar:
            members = _scan_members(tar, limits)
            _check_against_manifest(members, _read_manifest(tar, members))
            for f in manifest["dateien"]:
                member = members.get("data/" + f["pfad"])
                if member is None:
                    raise BackupError("Archiv hat sich seit der Prüfung verändert.")
                dest = staging.joinpath(*f["pfad"].split("/"))
                if staging.resolve() not in dest.resolve().parents:
                    raise BackupError("Unerlaubter Pfad im Archiv.")
                dest.parent.mkdir(parents=True, exist_ok=True)
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                with os.fdopen(os.open(str(dest), flags, 0o600), "wb") as fh:
                    digest = _copy_hashed(tar.extractfile(member), fh, f["bytes"])
                if digest != f["sha256"]:
                    raise BackupError(f"Archiv hat sich seit der Prüfung verändert: {f['pfad'][:80]!r}")
        os.chmod(str(staging), 0o700)
        os.rename(str(staging), str(target))     # gelingt nur, wenn das Ziel fehlt oder (noch) leer ist
    except BaseException as exc:
        shutil.rmtree(str(staging), ignore_errors=True)     # nur der eigene Zwischenordner
        if isinstance(exc, BackupError):
            raise
        if isinstance(exc, (tarfile.TarError, OSError, EOFError, ValueError, KeyError)):
            raise BackupError(f"Wiederherstellung abgebrochen ({exc.__class__.__name__}). Das Ziel wurde nicht "
                              f"verändert.") from exc
        raise
    return target


# ---------------------------------------------------------------------- Geordnetes Beenden
def install_stop_handler(stop) -> None:
    """SIGTERM (z. B. von systemd beim Stoppen) beendet JARVIS geordnet wie ctrl + C."""
    import signal
    import threading

    def handler(signum, frame):  # noqa: ARG001
        threading.Thread(target=stop, daemon=True).start()
    signal.signal(signal.SIGTERM, handler)
