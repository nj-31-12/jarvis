"""SQLite-Speicher des Studios. Eine Datei, keine Installation."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

FACT_STATUS = ("bestaetigt", "geruecht", "leak", "spekulation", "widerlegt")
VIDEO_STATUS = ("idee", "skript", "aufgenommen", "geschnitten", "geplant", "gepostet")

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'allgemein',
    status TEXT NOT NULL DEFAULT 'spekulation',
    source_name TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    used_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    series TEXT NOT NULL DEFAULT '',
    hook_type TEXT NOT NULL DEFAULT '',
    hook TEXT NOT NULL DEFAULT '',
    script TEXT NOT NULL DEFAULT '',
    onscreen TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    hashtags TEXT NOT NULL DEFAULT '',
    fact_ids TEXT NOT NULL DEFAULT '[]',
    target_seconds INTEGER NOT NULL DEFAULT 60,
    status TEXT NOT NULL DEFAULT 'idee',
    planned_at TEXT NOT NULL DEFAULT '',
    posted_at TEXT NOT NULL DEFAULT '',
    tiktok_url TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    captured_at TEXT NOT NULL,
    hours_after INTEGER NOT NULL DEFAULT 24,
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    saves INTEGER NOT NULL DEFAULT 0,
    avg_watch_seconds REAL NOT NULL DEFAULT 0,
    completion_pct REAL NOT NULL DEFAULT 0,
    followers_gained INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    handle TEXT NOT NULL UNIQUE,
    followers INTEGER NOT NULL DEFAULT 0,
    language TEXT NOT NULL DEFAULT 'de',
    focus TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS competitor_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    hook TEXT NOT NULL DEFAULT '',
    format TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    seconds INTEGER NOT NULL DEFAULT 0,
    posted_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

TABLE_FIELDS = {
    "facts": ("title", "detail", "category", "status", "source_name", "source_url", "used_count"),
    "videos": ("title", "series", "hook_type", "hook", "script", "onscreen", "caption", "hashtags",
               "fact_ids", "target_seconds", "status", "planned_at", "posted_at", "tiktok_url", "notes"),
    "metrics": ("video_id", "captured_at", "hours_after", "views", "likes", "comments", "shares", "saves",
                "avg_watch_seconds", "completion_pct", "followers_gained"),
    "competitors": ("handle", "followers", "language", "focus", "notes"),
    "competitor_posts": ("competitor_id", "title", "hook", "format", "url", "views", "likes", "comments",
                         "shares", "seconds", "posted_at"),
}
INT_FIELDS = {"used_count", "target_seconds", "video_id", "hours_after", "views", "likes", "comments", "shares",
              "saves", "followers_gained", "followers", "competitor_id", "seconds"}
FLOAT_FIELDS = {"avg_watch_seconds", "completion_pct"}
MAX_TEXT = 20_000

DEFAULT_SETTINGS = {
    "account_handle": "@dein.gta.account",
    "language": "de",
    "posts_per_day": "2",
    "post_times": "12:30,18:00,21:00",
    "release_date": "2026-11-19",
    "voice_wpm": "150",
}


class ValidationError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _clean(table: str, data: dict, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Ungültige Daten")
    out = {}
    for key in TABLE_FIELDS[table]:
        if key not in data:
            continue
        value = data[key]
        if key in INT_FIELDS:
            try:
                value = int(float(value or 0))
            except (TypeError, ValueError):
                raise ValidationError(f"{key} muss eine Zahl sein")
            if value < 0:
                raise ValidationError(f"{key} darf nicht negativ sein")
        elif key in FLOAT_FIELDS:
            try:
                value = float(value or 0)
            except (TypeError, ValueError):
                raise ValidationError(f"{key} muss eine Zahl sein")
            if value < 0:
                raise ValidationError(f"{key} darf nicht negativ sein")
        elif key == "fact_ids":
            if isinstance(value, str):
                try:
                    value = json.loads(value or "[]")
                except ValueError:
                    raise ValidationError("fact_ids ungültig")
            if not isinstance(value, list) or not all(isinstance(i, int) for i in value):
                raise ValidationError("fact_ids muss eine Liste von Zahlen sein")
            value = json.dumps(value)
        else:
            value = "" if value is None else str(value)
            if len(value) > MAX_TEXT:
                raise ValidationError(f"{key} ist zu lang")
            if key.endswith("url") and value and not value.startswith(("https://", "http://")):
                raise ValidationError("Links müssen mit https:// beginnen")
        out[key] = value
    if table == "facts" and "status" in out and out["status"] not in FACT_STATUS:
        raise ValidationError("Unbekannter Fakten-Status")
    if table == "videos" and "status" in out and out["status"] not in VIDEO_STATUS:
        raise ValidationError("Unbekannter Video-Status")
    if table == "metrics" and "completion_pct" in out and out["completion_pct"] > 100:
        raise ValidationError("completion_pct höchstens 100")
    if not partial:
        required = {"facts": "title", "videos": "title", "metrics": "video_id",
                    "competitors": "handle", "competitor_posts": "title"}[table]
        if not str(out.get(required, "")).strip():
            raise ValidationError(f"{required} fehlt")
    return out


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            for k, v in DEFAULT_SETTINGS.items():
                self._conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ generisch
    def list(self, table: str, where: str = "", params: tuple = (), order: str = "id DESC") -> list[dict]:
        self._check(table)
        sql = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "") + f" ORDER BY {order}"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row(table, r) for r in rows]

    def get(self, table: str, item_id: int) -> dict | None:
        self._check(table)
        with self._lock:
            row = self._conn.execute(f"SELECT * FROM {table} WHERE id = ?", (int(item_id),)).fetchone()
        return self._row(table, row) if row else None

    def create(self, table: str, data: dict) -> dict:
        clean = _clean(table, data)
        if table in ("facts", "videos"):
            clean["created_at"] = clean["updated_at"] = now_iso()
        elif table in ("competitors", "competitor_posts"):
            clean["created_at"] = now_iso()
        elif table == "metrics":
            clean.setdefault("captured_at", now_iso())
            if not self.get("videos", clean["video_id"]):
                raise ValidationError("Video existiert nicht")
        if table == "competitor_posts" and not self.get("competitors", clean.get("competitor_id", 0)):
            raise ValidationError("Konkurrent existiert nicht")
        cols = ", ".join(clean)
        marks = ", ".join("?" for _ in clean)
        with self._lock:
            try:
                cur = self._conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(clean.values()))
            except sqlite3.IntegrityError as exc:
                raise ValidationError("Eintrag existiert schon oder ist ungültig") from exc
            self._conn.commit()
            new_id = cur.lastrowid
        return self.get(table, new_id)

    def update(self, table: str, item_id: int, data: dict) -> dict | None:
        clean = _clean(table, data, partial=True)
        if not clean:
            return self.get(table, item_id)
        if table in ("facts", "videos"):
            clean["updated_at"] = now_iso()
        sets = ", ".join(f"{k} = ?" for k in clean)
        with self._lock:
            try:
                self._conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", tuple(clean.values()) + (int(item_id),))
            except sqlite3.IntegrityError as exc:
                raise ValidationError("Ungültige Änderung") from exc
            self._conn.commit()
        return self.get(table, item_id)

    def delete(self, table: str, item_id: int) -> bool:
        self._check(table)
        with self._lock:
            cur = self._conn.execute(f"DELETE FROM {table} WHERE id = ?", (int(item_id),))
            self._conn.commit()
        return cur.rowcount > 0

    def count(self, table: str) -> int:
        self._check(table)
        with self._lock:
            return self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # ------------------------------------------------------------------ Einstellungen
    def settings(self) -> dict:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def set_settings(self, data: dict) -> dict:
        if not isinstance(data, dict):
            raise ValidationError("Ungültige Daten")
        with self._lock:
            for k, v in data.items():
                if k not in DEFAULT_SETTINGS:
                    continue
                v = str(v)[:500]
                self._conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (k, v))
            self._conn.commit()
        return self.settings()

    # ------------------------------------------------------------------ intern
    @staticmethod
    def _check(table: str) -> None:
        if table not in TABLE_FIELDS:
            raise ValidationError("Unbekannte Tabelle")

    @staticmethod
    def _row(table: str, row: sqlite3.Row) -> dict:
        d = dict(row)
        if table == "videos":
            try:
                d["fact_ids"] = json.loads(d.get("fact_ids") or "[]")
            except ValueError:
                d["fact_ids"] = []
        return d
