"""Version 5.1: Sicherheitstests für Sicherungsarchive (Prüfung und Wiederherstellung).

Jeder Test baut ein kleines, absichtlich manipuliertes Archiv und erwartet eine klare Ablehnung –
ohne dass im Zielordner etwas entsteht.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis import server
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis
from jarvis.server import BackupError, BackupLimits, MANIFEST


def entry(rel: str, content: bytes) -> dict:
    return {"pfad": rel, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, files, manifest=None, extra=(), name="a.tar.gz"):
        """files: [(pfad, inhalt)] unter data/. manifest: eigenes Manifest (sonst passend). extra: TarInfo-Einträge."""
        if manifest is None:
            manifest = {"erstellt": "x", "dateien": [entry(rel, c) for rel, c in files]}
        raw = manifest if isinstance(manifest, bytes) else json.dumps(manifest).encode()
        path = self.tmp / name
        with tarfile.open(str(path), "w:gz") as t:
            for rel, content in files:
                info = tarfile.TarInfo("data/" + rel)
                info.size = len(content)
                t.addfile(info, io.BytesIO(content))
            for info, content in extra:
                t.addfile(info, io.BytesIO(content) if content is not None else None)
            info = tarfile.TarInfo(MANIFEST)
            info.size = len(raw)
            t.addfile(info, io.BytesIO(raw))
        return path

    def assert_rejected(self, archive, contains="", limits=server.LIMITS):
        with self.assertRaises(BackupError) as ctx:
            server.verify_backup(archive, limits)
        self.assertIn(contains, str(ctx.exception))
        target = self.tmp / "ziel"
        with self.assertRaises(BackupError):
            server.restore_backup(archive, target, limits)
        self.assertFalse(target.exists(), "Ziel darf bei Ablehnung nicht entstehen")
        self.assertEqual([p.name for p in self.tmp.iterdir() if "wiederherstellung" in p.name], [],
                         "kein Zwischenordner darf übrig bleiben")

    def test_valid_small_archive_is_accepted(self):
        a = self.build([("audit.jsonl", b"{}\n"), ("vault/00_Inbox/JARVIS/Notiz ä.md", b"# Hallo")])
        self.assertEqual(len(server.verify_backup(a)["dateien"]), 2)
        out = server.restore_backup(a, self.tmp / "neu")
        self.assertEqual((out / "vault" / "00_Inbox" / "JARVIS" / "Notiz ä.md").read_bytes(), b"# Hallo")


class SizeLimits(Base):
    def test_archive_file_too_large(self):
        a = self.build([("x", b"a" * 1000)])
        self.assert_rejected(a, "größer als erlaubt", BackupLimits(archive_bytes=50))

    def test_total_unpacked_size_limited(self):
        a = self.build([("a", b"x" * 600), ("b", b"y" * 600)])
        self.assert_rejected(a, "Gesamtgröße", BackupLimits(total_bytes=1000))

    def test_single_file_size_limited(self):
        a = self.build([("gross", b"z" * 5000)])
        self.assert_rejected(a, "zu groß", BackupLimits(file_bytes=4000))

    def test_compression_bomb_stops_early(self):
        a = self.build([("bombe", b"\0" * (3 * 1024 * 1024))])          # komprimiert winzig, entpackt 3 MiB
        self.assertLess(a.stat().st_size, 20_000)
        self.assert_rejected(a, "zu groß", BackupLimits(file_bytes=1024 * 1024))

    def test_too_many_entries(self):
        a = self.build([(f"f{i}", b"x") for i in range(20)])
        self.assert_rejected(a, "Zu viele", BackupLimits(entries=10))

    def test_manifest_size_limited(self):
        a = self.build([("a", b"x")])
        self.assert_rejected(a, "zu groß", BackupLimits(manifest_bytes=10))

    def test_declared_size_must_match_manifest(self):
        m = {"dateien": [dict(entry("a", b"abc"), bytes=2)]}
        self.assert_rejected(self.build([("a", b"abc")], m), "Größe stimmt nicht")


class Duplicates(Base):
    def test_duplicate_archive_entries_rejected(self):
        info = tarfile.TarInfo("data/a")
        info.size = 4
        a = self.build([("a", b"gut1")], extra=[(info, b"BOSE")])     # zweiter Eintrag gleichen Namens
        self.assert_rejected(a, "Doppelter Eintrag")

    def test_duplicate_manifest_paths_rejected(self):
        m = {"dateien": [entry("a", b"x"), entry("a", b"x")]}
        self.assert_rejected(self.build([("a", b"x")], m), "Doppelter Pfad")

    def test_duplicate_manifest_file_rejected(self):
        info = tarfile.TarInfo(MANIFEST)
        info.size = 2
        a = self.build([("a", b"x")], extra=[(info, b"{}")])
        self.assert_rejected(a, "Doppelter Eintrag")


class PathsAndTypes(Base):
    BAD_PATHS = ["../ausbruch", "/etc/passwd", "a/../../b", "a//b", "./a", "a/./b", "a/", "", "a\\b",
                 "nul\x00byte", "zeile\numbruch", "tab\tx", "x" * 300]

    def test_bad_paths_in_manifest_rejected(self):
        for bad in self.BAD_PATHS:
            with self.subTest(repr(bad)):
                m = {"dateien": [{"pfad": bad, "bytes": 1, "sha256": "0" * 64}]}
                self.assert_rejected(self.build([("ok", b"x")], m, name="m.tar.gz"))

    def test_manifest_path_check_works_on_its_own(self):
        """Die Manifest-Prüfung allein (unabhängig vom Abgleich mit den Archiveinträgen)."""
        for bad in self.BAD_PATHS:
            with self.subTest(repr(bad)):
                raw = json.dumps({"dateien": [{"pfad": bad, "bytes": 1, "sha256": "0" * 64}]}).encode()
                path = self.tmp / "nur-manifest.tar.gz"
                with tarfile.open(str(path), "w:gz") as t:
                    info = tarfile.TarInfo(MANIFEST)
                    info.size = len(raw)
                    t.addfile(info, io.BytesIO(raw))
                with tarfile.open(str(path), "r:gz") as t:
                    members = server._scan_members(t, server.LIMITS)
                    with self.assertRaises(BackupError):
                        server._read_manifest(t, members)
        for good in ("a", "vault/00_Inbox/JARVIS/2026-11-01 Notiz ä (2).md", "audit.jsonl"):
            self.assertTrue(server.valid_backup_path(good))

    def test_bad_member_names_rejected(self):
        for bad in ["../ausbruch", "/abs", "data/../x", "data/a//b", "data/", "anders/x", "data/a\\b"]:
            with self.subTest(repr(bad)):
                info = tarfile.TarInfo(bad)
                info.size = 1
                self.assert_rejected(self.build([("ok", b"x")], extra=[(info, b"x")], name="n.tar.gz"), "Unerlaubter")

    def test_only_regular_files_allowed(self):
        kinds = {"Symlink": tarfile.SYMTYPE, "Hardlink": tarfile.LNKTYPE, "Ordner": tarfile.DIRTYPE,
                 "Gerät": tarfile.CHRTYPE, "FIFO": tarfile.FIFOTYPE}
        for label, kind in kinds.items():
            with self.subTest(label):
                info = tarfile.TarInfo("data/link")
                info.type = kind
                info.linkname = "/etc/passwd" if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ""
                self.assert_rejected(self.build([("ok", b"x")], extra=[(info, None)], name="t.tar.gz"),
                                     "Eintragstyp")

    def test_manifest_structure_checked(self):
        cases = {"kein JSON": b"{kaputt", "keine Liste": {"dateien": "x"}, "kein Objekt": [1, 2],
                 "Eintrag kein Objekt": {"dateien": ["a"]},
                 "bytes als Text": {"dateien": [dict(entry("a", b"x"), bytes="1")]},
                 "bytes negativ": {"dateien": [dict(entry("a", b"x"), bytes=-1)]},
                 "bytes bool": {"dateien": [dict(entry("a", b"x"), bytes=True)]},
                 "sha kein hex": {"dateien": [dict(entry("a", b"x"), sha256="z" * 64)]},
                 "sha zu kurz": {"dateien": [dict(entry("a", b"x"), sha256="ab")]}}
        for label, m in cases.items():
            with self.subTest(label):
                self.assert_rejected(self.build([("a", b"x")], m, name="s.tar.gz"))

    def test_missing_or_extra_files_rejected(self):
        self.assert_rejected(self.build([("a", b"x")], {"dateien": []}), "stimmen nicht")
        self.assert_rejected(self.build([("a", b"x")], {"dateien": [entry("a", b"x"), entry("b", b"y")]}),
                             "stimmen nicht")

    def test_wrong_checksum_rejected(self):
        self.assert_rejected(self.build([("a", b"echt")], {"dateien": [entry("a", b"fals")]}), "Prüfsumme")

    def test_archive_must_be_regular_file(self):
        real = self.build([("a", b"x")])
        link = self.tmp / "link.tar.gz"
        os.symlink(str(real), str(link))
        self.assert_rejected(link, "keine normale Datei")
        self.assert_rejected(self.tmp / "fehlt.tar.gz", "nicht gefunden")

    def test_not_a_gzip_archive(self):
        bad = self.tmp / "kaputt.tar.gz"
        bad.write_bytes(b"kein archiv" * 10)
        self.assert_rejected(bad, "beschädigt")


class RestoreSafety(Base):
    def test_archive_changed_after_verification_is_detected(self):
        good = self.build([("a", b"echt")], name="gut.tar.gz")
        manifest = server.verify_backup(good)
        swapped = self.build([("a", b"BOSE")], {"dateien": [entry("a", b"echt")]}, name="getauscht.tar.gz")
        target = self.tmp / "ziel"
        with mock.patch.object(server, "verify_backup", return_value=manifest):    # Prüfung „vorher“ war gut …
            with self.assertRaises(BackupError) as ctx:
                server.restore_backup(swapped, target)                             # … Archiv inzwischen getauscht
        self.assertIn("verändert", str(ctx.exception))
        self.assertFalse(target.exists())
        self.assertEqual([p for p in self.tmp.iterdir() if "wiederherstellung" in p.name], [])

    def test_restore_into_existing_empty_folder_and_never_into_full(self):
        a = self.build([("a", b"x")])
        empty = self.tmp / "leer"
        empty.mkdir()
        server.restore_backup(a, empty)
        self.assertEqual((empty / "a").read_bytes(), b"x")
        with self.assertRaises(BackupError):
            server.restore_backup(a, empty)                     # jetzt voll → abgelehnt
        f = self.tmp / "datei"
        f.write_text("x")
        with self.assertRaises(BackupError):
            server.restore_backup(a, f)                         # Ziel ist eine Datei → abgelehnt
        self.assertEqual(f.read_text(), "x")

    def test_restored_files_are_private(self):
        out = server.restore_backup(self.build([("sub/a", b"x")]), self.tmp / "neu")
        self.assertEqual((out / "sub" / "a").stat().st_mode & 0o777, 0o600)
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)


class MakeBackupRules(Base):
    def setUp(self):
        super().setUp()
        self.data = self.tmp / "data"
        self.cfg = dict(DEFAULTS, data_dir=str(self.data), vault_dir=str(self.data / "vault"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1},
                        backup={"dir": str(self.tmp / "sicherungen")})
        Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None).close()

    def test_unsafe_file_name_gives_clear_error_and_no_partial_archive(self):
        (self.data / "vault").mkdir(parents=True, exist_ok=True)
        (self.data / "vault" / "schlecht\\name.md").write_text("x", encoding="utf-8")
        with self.assertRaises(BackupError) as ctx:
            server.make_backup(self.cfg)
        self.assertIn("umbenennen", str(ctx.exception))
        self.assertEqual(list((self.tmp / "sicherungen").iterdir()), [])        # keine halbe Datei

    def test_backup_respects_limits(self):
        (self.data / "gross.bin").write_bytes(b"x" * 5000)
        with self.assertRaises(BackupError):
            server.make_backup(self.cfg, limits=BackupLimits(file_bytes=4000))
        self.assertEqual(list((self.tmp / "sicherungen").iterdir()), [])

    def test_normal_backup_roundtrip_still_works(self):
        archive = server.make_backup(self.cfg)
        out = server.restore_backup(archive, self.tmp / "zurueck")
        self.assertTrue((out / "actions.db").exists())


if __name__ == "__main__":
    unittest.main()
