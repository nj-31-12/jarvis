"""Version 5 · Phase D: Server-Vorbereitung (Pfade, Zugangsdaten, Start/Stopp, Gesundheit, Sicherung)."""
from __future__ import annotations

import io
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from jarvis import server
from jarvis.config import DEFAULTS, PROJECT_ROOT, load_config, load_secrets
from jarvis.core import Jarvis

SECRET = "z" * 48


class Child:
    """Unterprozess für Tests (Version 5.1).

    - Ausgaben gehen in Dateien statt in Pipes: Es kann nie ein Lesen ohne Ende geben.
    - wait_for() wartet höchstens `timeout` Sekunden und meldet sonst klar, was passiert ist (inkl. Fehlerausgabe).
    - Beim Verlassen wird der Prozess IMMER beendet (erst SIGTERM-frei per kill, dann wait mit Zeitlimit).
    - PYTHONUNBUFFERED wird bewusst entfernt: So fällt auf, wenn eine Meldung ohne flush gepuffert bleibt.
    """

    def __init__(self, args, folder: Path, name: str):
        env = dict(os.environ)
        env.pop("PYTHONUNBUFFERED", None)
        self.out_path, self.err_path = folder / f"{name}.out", folder / f"{name}.err"
        self._out = self.out_path.open("wb")
        self._err = self.err_path.open("wb")
        self.proc = subprocess.Popen(args, stdout=self._out, stderr=self._err, env=env)

    def output(self) -> str:
        return self.out_path.read_text(encoding="utf-8", errors="replace")

    def errors(self) -> str:
        return self.err_path.read_text(encoding="utf-8", errors="replace")

    def wait_for(self, marker: str, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if marker in self.output():
                return
            if self.proc.poll() is not None:
                raise AssertionError(f"Unterprozess vor „{marker}“ beendet (Rückgabe {self.proc.returncode}).\n"
                                     f"Ausgabe: {self.output()[-800:]}\nFehler: {self.errors()[-2000:]}")
            time.sleep(0.05)
        raise AssertionError(f"„{marker}“ kam nicht innerhalb von {timeout:.0f} s (Startproblem oder gepufferte "
                             f"Ausgabe).\nAusgabe: {self.output()[-800:]}\nFehler: {self.errors()[-2000:]}")

    def wait_exit(self, timeout: float = 20.0) -> int:
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"Unterprozess hat sich nicht innerhalb von {timeout:.0f} s beendet.\n"
                                 f"Fehler: {self.errors()[-2000:]}") from None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.proc.poll() is None:
            self.proc.kill()
        try:
            self.proc.wait(timeout=10)
        finally:
            self._out.close()
            self._err.close()
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.data.mkdir(mode=0o700)
        os.chmod(str(self.data), 0o700)
        self.cfg = dict(DEFAULTS, data_dir=str(self.data), vault_dir=str(self.data / "vault"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1},
                        backup={"dir": str(self.tmp / "sicherungen")})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def jarvis_with_data(self):
        j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        j.handle_text("/mail coach@example.com | Hallo | Text")
        j.handle_text("/notiz Testnotiz für die Sicherung")
        return j


class ConfigurablePaths(Base):
    def test_d1_environment_overrides_paths(self):
        cfgfile = self.tmp / "jarvis.json"
        cfgfile.write_text("{}", encoding="utf-8")
        env = {"JARVIS_CONFIG": str(cfgfile), "JARVIS_DATA_DIR": str(self.tmp / "x"),
               "JARVIS_VAULT_DIR": str(self.tmp / "v"), "JARVIS_BACKUP_DIR": str(self.tmp / "b")}
        with mock.patch.dict(os.environ, env):
            cfg = load_config()
        self.assertEqual(cfg["data_dir"], str(self.tmp / "x"))
        self.assertEqual(cfg["vault_dir"], str(self.tmp / "v"))
        self.assertEqual(cfg["backup"]["dir"], str(self.tmp / "b"))

    def test_d1_named_config_must_exist(self):
        with mock.patch.dict(os.environ, {"JARVIS_CONFIG": str(self.tmp / "fehlt.json")}):
            with self.assertRaises(ValueError):
                load_config()

    def test_d1_invalid_mode_and_public_host_refused(self):
        for bad in ({"server": {"mode": "egal"}}, {"web": {"host": "0.0.0.0"}}):
            f = self.tmp / "c.json"
            f.write_text(json.dumps(bad), encoding="utf-8")
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    load_config(f)

    def test_d1_default_backup_dir_outside_data(self):
        cfg = load_config(self.tmp / "gibtsnicht.json")
        self.assertNotIn(cfg["data_dir"], cfg["backup"]["dir"])


class Credentials(Base):
    def test_d2_systemd_credentials_and_key_variables(self):
        cred = self.tmp / "cred"
        cred.mkdir()
        (cred / "JARVIS_APPROVAL_SECRET").write_text(SECRET + "\n", encoding="utf-8")
        (cred / "fremd.txt").write_text("nicht laden", encoding="utf-8")
        env = {"CREDENTIALS_DIRECTORY": str(cred), "JARVIS_OPENROUTER_KEY": "testwert"}
        with mock.patch.dict(os.environ, env):
            sec = load_secrets(self.tmp / "keine.env")
        self.assertEqual(sec["JARVIS_APPROVAL_SECRET"], SECRET)
        self.assertEqual(sec["JARVIS_OPENROUTER_KEY"], "testwert")
        self.assertNotIn("fremd.txt", sec)

    def test_d2_no_secrets_in_deploy_templates(self):
        for f in (PROJECT_ROOT / "deploy").rglob("*"):
            if f.is_file():
                text = f.read_text(encoding="utf-8")
                with self.subTest(f.name):
                    self.assertNotRegex(text, r"(?i)(SECRET|TOKEN|KEY)\s*=\s*\S{8,}")
                    self.assertNotIn("0.0.0.0", text)


class StartStop(Base):
    def test_d3_second_instance_is_refused(self):
        with server.instance_lock(self.data, "web"):
            with self.assertRaises(server.AlreadyRunning):
                with server.instance_lock(self.data, "web"):
                    pass
            with server.instance_lock(self.data, "aufgaben"):     # andere Rolle ist unabhängig
                pass
        with server.instance_lock(self.data, "web"):              # nach Ende wieder frei
            pass

    def test_d3_lock_works_across_processes_and_is_released_after_crash(self):
        code = ("import sys,time; sys.path.insert(0, sys.argv[1]); from jarvis import server\n"
                "with server.instance_lock(sys.argv[2], 'web'):\n print('gesperrt', flush=True); time.sleep(60)")
        with Child([sys.executable, "-c", code, str(PROJECT_ROOT), str(self.data)], self.tmp, "sperre") as child:
            child.wait_for("gesperrt")
            with self.assertRaises(server.AlreadyRunning):
                with server.instance_lock(self.data, "web"):
                    pass
            child.proc.kill()                                  # simulierter Absturz
            child.wait_exit()
        with server.instance_lock(self.data, "web"):
            pass

    def _server_script(self, port: int = 0) -> Path:
        script = self.tmp / "start.py"
        script.write_text(f"""
import sys; sys.path.insert(0, {str(PROJECT_ROOT)!r})
from jarvis import web_auth as wa
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis
from jarvis.web import WebApp, serve
cfg = dict(DEFAULTS, data_dir={str(self.data)!r}, vault_dir={str(self.data / 'vault')!r},
           telegram={{"allowed_user_ids": [1], "approval_chat_id": 1}}, web=dict(DEFAULTS["web"], port={port}))
j = Jarvis(cfg, {{"JARVIS_APPROVAL_SECRET": "z" * 48}}, channel=lambda *a: None)
app = WebApp(cfg, wa.AuthStore({str(self.data)!r}, j.audit), j)
app.quiet = True
serve(app, "127.0.0.1")
""", encoding="utf-8")
        return script

    def test_d7_sigterm_stops_web_server_cleanly(self):
        with Child([sys.executable, str(self._server_script())], self.tmp, "web") as child:
            child.wait_for("JARVIS läuft")                     # ohne flush: klare Meldung nach 20 s statt Hängen
            child.proc.send_signal(signal.SIGTERM)
            code = child.wait_exit()
            self.assertEqual(code, 0, child.errors())
            self.assertIn("Datenbanken geschlossen", child.output())
        from jarvis.audit import AuditLog
        self.assertTrue(AuditLog(self.data / "audit.jsonl").verify()[0])

    def test_d7_failed_server_start_gives_clear_message_and_no_hang(self):
        import socket
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))                         # Port ist schon belegt → Start muss scheitern
        blocker.listen(1)
        port = blocker.getsockname()[1]
        try:
            with Child([sys.executable, str(self._server_script(port))], self.tmp, "belegt") as child:
                with self.assertRaises(AssertionError) as ctx:
                    child.wait_for("JARVIS läuft", timeout=20)
                self.assertIn("beendet", str(ctx.exception))      # klarer Grund statt Warten
                self.assertIn("OSError", str(ctx.exception))      # Ursache (Port belegt) steht in der Meldung
                self.assertNotEqual(child.proc.returncode, 0)
        finally:
            blocker.close()

    def test_d7_helper_never_waits_forever(self):
        code = "import time; print('ohne flush'); time.sleep(60)"     # gepufferte Ausgabe, wie der alte Fehler
        start = time.monotonic()
        with Child([sys.executable, "-c", code], self.tmp, "puffer") as child:
            with self.assertRaises(AssertionError) as ctx:
                child.wait_for("ohne flush", timeout=2)
            self.assertIn("gepufferte", str(ctx.exception))
        self.assertLess(time.monotonic() - start, 15)
        self.assertIsNotNone(child.proc.poll())                       # Unterprozess wurde beendet


class Preflight(Base):
    def test_d4_permissions_are_errors_in_server_mode_only(self):
        os.chmod(str(self.data), 0o755)
        local = dict(self.cfg, server={"mode": "lokal"})
        srv = dict(self.cfg, server={"mode": "server"})
        env = self.tmp / ".env"
        self.assertIn("warnung", [l for l, _ in server.preflight(local, env)])
        self.assertIn("fehler", [l for l, _ in server.preflight(srv, env)])

    def test_d4_readable_env_file_is_an_error(self):
        env = self.tmp / ".env"
        env.write_text("JARVIS_APPROVAL_SECRET=x", encoding="utf-8")
        os.chmod(str(env), 0o644)
        self.assertIn("fehler", [l for l, _ in server.preflight(self.cfg, env)])
        os.chmod(str(env), 0o600)
        self.assertEqual([l for l, _ in server.preflight(self.cfg, env)], ["ok"])

    def test_d4_public_host_is_an_error(self):
        cfg = dict(self.cfg, web=dict(DEFAULTS["web"], host="0.0.0.0"))
        self.assertIn("fehler", [l for l, _ in server.preflight(cfg, self.tmp / ".env")])


class Health(Base):
    def test_d5_healthy_system_after_backup(self):
        self.jarvis_with_data().close()
        server.make_backup(self.cfg)
        report = server.health_report(self.cfg)
        self.assertEqual(server.health_exit_code(report), 0, report)

    def test_d5_missing_backup_and_killswitch_are_warnings(self):
        j = self.jarvis_with_data()
        j.kill.activate("Test")
        j.close()
        report = server.health_report(self.cfg)
        self.assertEqual(server.health_exit_code(report), 1)
        self.assertTrue(any(a == "Sicherung" for _, a, _ in report))
        self.assertTrue(any(a == "Notaus" and l == "warnung" for l, a, _ in report))

    def test_d5_corrupt_database_or_log_is_an_error(self):
        self.jarvis_with_data().close()
        (self.data / "kaputt.db").write_bytes(b"keine datenbank" * 100)
        self.assertEqual(server.health_exit_code(server.health_report(self.cfg)), 2)
        (self.data / "kaputt.db").unlink()
        log = self.data / "audit.jsonl"
        log.write_text(log.read_text(encoding="utf-8").replace("proposed", "proposeX"), encoding="utf-8")
        self.assertEqual(server.health_exit_code(server.health_report(self.cfg)), 2)

    def test_d5_missing_data_dir_is_an_error(self):
        cfg = dict(self.cfg, data_dir=str(self.tmp / "fehlt"))
        self.assertEqual(server.health_exit_code(server.health_report(cfg)), 2)

    def test_d5_health_check_changes_nothing(self):
        # Version 5.2: strenger als vorher (zusätzlich Zeitstempel) und mit Angabe der betroffenen Datei
        from jarvis.__main__ import data_fingerprint
        from tests.test_v5_2_nur_lesen import describe_changes, strict_snapshot
        self.jarvis_with_data().close()
        before, strict_before = data_fingerprint(self.data)[1], strict_snapshot(self.data)
        server.health_report(self.cfg)
        strict_after = strict_snapshot(self.data)
        self.assertEqual(strict_after, strict_before, describe_changes(strict_before, strict_after))
        self.assertEqual(data_fingerprint(self.data)[1], before)

    def test_d9_cli_exit_code(self):
        from jarvis import __main__ as cli
        self.jarvis_with_data().close()
        with mock.patch.object(cli, "load_config", return_value=self.cfg), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["jarvis", "gesundheit"])
        self.assertEqual(ctx.exception.code, 1)       # Warnung: noch keine Sicherung


class Backup(Base):
    def test_d6_backup_is_complete_consistent_and_private(self):
        j = self.jarvis_with_data()
        # Schreibvorgang, der noch nur in der -wal-Datei steht (JARVIS läuft weiter)
        j.gate.propose("send_email", {"an": "b@example.com"}, "noch im WAL")
        archive = server.make_backup(self.cfg)
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        manifest = server.verify_backup(archive)
        names = {f["pfad"] for f in manifest["dateien"]}
        self.assertIn("actions.db", names)
        self.assertIn("audit.jsonl", names)
        self.assertFalse(any(n.endswith(("-wal", "-shm")) or n.startswith(".lock") for n in names))
        target = server.restore_backup(archive, self.tmp / "neu")
        con = sqlite3.connect(str(target / "actions.db"))
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM actions").fetchone()[0], 2)
        finally:
            con.close()
        j.close()

    def test_d6_never_overwrites(self):
        self.jarvis_with_data().close()
        fixed = lambda: 1_800_000_000.0  # noqa: E731
        a = server.make_backup(self.cfg, clock=fixed)
        b = server.make_backup(self.cfg, clock=fixed)
        self.assertNotEqual(a, b)
        self.assertTrue(a.exists() and b.exists())

    def test_d6_backup_dir_inside_data_refused(self):
        with self.assertRaises(server.BackupError):
            server.make_backup(self.cfg, self.data / "sicherungen")

    def test_d6_restore_only_into_empty_folder(self):
        self.jarvis_with_data().close()
        archive = server.make_backup(self.cfg)
        with self.assertRaises(server.BackupError):
            server.restore_backup(archive, self.data)          # bestehende Daten: niemals überschreiben
        restored = server.restore_backup(archive, self.tmp / "neu")
        from jarvis.__main__ import data_fingerprint
        original = {r: d for r, _, d in data_fingerprint(self.data)[0] if not r.endswith((".db", "-wal", "-shm")) and "lock" not in r}
        copy = {r: d for r, _, d in data_fingerprint(restored)[0] if not r.endswith(".db")}
        self.assertEqual(original, copy)

    def test_d6_tampered_or_foreign_archive_rejected(self):
        self.jarvis_with_data().close()
        archive = server.make_backup(self.cfg)
        bad = self.tmp / "manipuliert.tar.gz"
        with tarfile.open(str(archive), "r:gz") as src, tarfile.open(str(bad), "w:gz") as dst:
            for m in src.getmembers():
                content = src.extractfile(m).read()
                if m.name == "data/audit.jsonl":
                    content = content.replace(b"proposed", b"proposeX")
                m.size = len(content)
                dst.addfile(m, io.BytesIO(content))
        with self.assertRaises(server.BackupError):
            server.verify_backup(bad)
        evil = self.tmp / "boese.tar.gz"
        with tarfile.open(str(evil), "w:gz") as t:
            info = tarfile.TarInfo("../../etc/x")
            info.size = 1
            t.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(server.BackupError):
            server.restore_backup(evil, self.tmp / "ziel")
        self.assertFalse((self.tmp / "ziel").exists())


class Templates(unittest.TestCase):
    def test_d10_systemd_units_restart_and_hardening(self):
        unit = (PROJECT_ROOT / "deploy" / "systemd" / "jarvis-web.service").read_text(encoding="utf-8")
        for needed in ("Restart=on-failure", "NoNewPrivileges=yes", "ProtectSystem=strict",
                       "ReadWritePaths=/var/lib/jarvis", "KillSignal=SIGTERM", "LoadCredential=", "UMask=0077"):
            self.assertIn(needed, unit)
        cfg = json.loads((PROJECT_ROOT / "deploy" / "jarvis.server.example.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["web"]["host"], "127.0.0.1")
        self.assertFalse(cfg["privacy"]["external_ai_allowed"])


if __name__ == "__main__":
    unittest.main()
