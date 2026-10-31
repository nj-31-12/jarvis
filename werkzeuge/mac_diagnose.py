"""Diagnose für macOS (Version 5.2) – berührt KEINE echten JARVIS-Daten.

Start im Projektordner:   python3 werkzeuge/mac_diagnose.py

Was passiert:
  1. Ein NEUER temporärer Ordner wird angelegt (z. B. /var/folders/…/jarvis-diagnose-…).
  2. Dort entstehen Test-Datenbanken; es wird geprüft, ob SQLite auf diesem Mac -wal/-shm nach dem Schließen stehen lässt.
  3. Die Gesundheitsprüfung läuft auf diesem Testordner; jede veränderte Datei wird genannt.
  4. Der temporäre Ordner wird am Ende wieder entfernt (nur dieser).
Dein Ordner data/ wird weder gelesen noch verändert.
"""
from __future__ import annotations

import hashlib
import platform
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis import server                      # noqa: E402
from jarvis.config import DEFAULTS             # noqa: E402
from jarvis.core import Jarvis                 # noqa: E402


def snapshot(folder: Path) -> dict:
    out = {".": folder.stat().st_mtime_ns}
    for p in sorted(folder.rglob("*")):
        st = p.stat()
        out[p.relative_to(folder).as_posix()] = (
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "ordner", st.st_size, st.st_mtime_ns)
    return out


def main() -> None:
    print(f"Python {platform.python_version()} · SQLite {sqlite3.sqlite_version} · {platform.platform()}")
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-diagnose-"))
    try:
        probe = tmp / "probe.db"
        con = sqlite3.connect(str(probe))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE t (x)")
        con.commit()
        con.close()
        left = [p.name for p in tmp.iterdir() if p.name.startswith("probe.db-")]
        print("Hilfsdateien nach dem Schließen:", ", ".join(left) if left else "keine",
              "→ persistentes WAL (typisch macOS)" if left else "→ werden gelöscht (typisch Linux)")

        data = tmp / "data"
        cfg = dict(DEFAULTS, data_dir=str(data), vault_dir=str(data / "vault"),
                   telegram={"allowed_user_ids": [1], "approval_chat_id": 1}, backup={"dir": str(tmp / "sich")})
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        j.handle_text("/mail test@example.com | Diagnose | Text")
        j.close()
        before = snapshot(data)
        server.health_report(cfg)
        after = snapshot(data)
        changed = [k for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)]
        if changed:
            print("❌ Die Gesundheitsprüfung hat im Testordner etwas verändert:")
            for k in changed:
                print("   -", k, "NEU" if k not in before else "verändert")
        else:
            print("✅ Die Gesundheitsprüfung hat im Testordner nichts verändert (auch keine Zeitstempel).")
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    print("Temporärer Ordner entfernt. Deine echten Daten wurden nicht berührt.")


if __name__ == "__main__":
    main()
