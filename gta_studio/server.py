"""Lokaler Webserver mit JSON-API. Nur 127.0.0.1, keine fremden Skripte, kein automatisches Posten.

Schutz: Host-Prüfung (gegen DNS-Rebinding), Größenlimit, jede API-Anfrage braucht den Header
`X-Studio: 1` (fremde Webseiten können ihn ohne Erlaubnis nicht setzen), strenge Sicherheits-Header.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import analytics, generator as gen
from .db import FACT_STATUS, VIDEO_STATUS, Store, ValidationError

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 2 * 1024 * 1024
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
SECURITY_HEADERS = [
    ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                "media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
    ("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)"),
]
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}

CRUD = {"facts": "facts", "videos": "videos", "metrics": "metrics", "competitors": "competitors",
        "competitor-posts": "competitor_posts"}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class Studio:
    """Die eigentliche Logik, unabhängig vom HTTP-Server (gut testbar)."""

    def __init__(self, store: Store):
        self.store = store

    # -------------------------------------------------------------- Routing
    def handle(self, method: str, path: str, query: dict, body: dict | None):
        parts = [p for p in path.split("/") if p][1:]  # ohne "api"
        if not parts:
            raise ApiError(404, "Nicht gefunden")
        head = parts[0]
        if head == "meta" and method == "GET":
            return self.meta()
        if head == "dashboard" and method == "GET":
            return self.dashboard()
        if head == "settings":
            if method == "GET":
                return self.store.settings()
            if method == "PUT":
                return self.store.set_settings(body or {})
        if head == "generate" and method == "POST" and len(parts) == 2:
            return self.generate(parts[1], body or {})
        if head == "ideas" and method == "GET":
            return gen.ideas_from_facts(self.store.list("facts"), limit=int(query.get("limit", 12)))
        if head == "plan" and method == "POST":
            return self.plan(body or {})
        if head == "analytics" and method == "GET":
            return analytics.overview(self.store.list("videos"), self.store.list("metrics"))
        if head == "competitors" and len(parts) == 2 and parts[1] == "report" and method == "GET":
            return analytics.competitor_report(self.store.list("competitors"), self.store.list("competitor_posts"))
        if head == "metrics" and len(parts) == 2 and parts[1] == "import" and method == "POST":
            return self.import_metrics(body or {})
        if head == "videos" and len(parts) == 3 and parts[2] == "srt" and method == "GET":
            return self.srt(parts[1])
        if head == "videos" and len(parts) == 3 and parts[2] == "posted" and method == "POST":
            return self.mark_posted(parts[1], body or {})
        if head == "export" and method == "GET":
            data = {t: self.store.list(CRUD[t]) for t in CRUD}
            data.update(settings=self.store.settings(), exported_at=datetime.now().isoformat())
            return data
        if head in CRUD:
            return self.crud(CRUD[head], method, parts[1:], query, body)
        raise ApiError(404, "Nicht gefunden")

    def crud(self, table: str, method: str, rest: list, query: dict, body: dict | None):
        if not rest:
            if method == "GET":
                where, params = "", ()
                if table == "metrics" and query.get("video_id"):
                    where, params = "video_id = ?", (int(query["video_id"]),)
                if table == "competitor_posts" and query.get("competitor_id"):
                    where, params = "competitor_id = ?", (int(query["competitor_id"]),)
                if table == "videos" and query.get("status"):
                    where, params = "status = ?", (query["status"],)
                order = "planned_at = '', planned_at, id DESC" if table == "videos" else "id DESC"
                return self.store.list(table, where, params, order)
            if method == "POST":
                item = self.store.create(table, body or {})
                if table == "videos":
                    self._count_facts(item.get("fact_ids", []))
                return item
            raise ApiError(405, "Methode nicht erlaubt")
        if not rest[0].isdigit():
            raise ApiError(404, "Nicht gefunden")
        item_id = int(rest[0])
        if method == "GET":
            item = self.store.get(table, item_id)
        elif method == "PUT":
            item = self.store.update(table, item_id, body or {})
        elif method == "DELETE":
            if not self.store.delete(table, item_id):
                raise ApiError(404, "Nicht gefunden")
            return {"deleted": item_id}
        else:
            raise ApiError(405, "Methode nicht erlaubt")
        if item is None:
            raise ApiError(404, "Nicht gefunden")
        return item

    # -------------------------------------------------------------- Funktionen
    def meta(self) -> dict:
        return {
            "hooks": [{"type": k, "template": v[0], "trigger": v[1]} for k, v in gen.HOOKS.items()],
            "series": [{"name": k, "description": v} for k, v in gen.SERIES.items()],
            "fact_status": [{"key": k, "label": gen.STATUS_LABEL[k]} for k in FACT_STATUS],
            "video_status": list(VIDEO_STATUS),
            "checklist": gen.PRE_POST_CHECKLIST,
        }

    def dashboard(self) -> dict:
        settings = self.store.settings()
        videos = self.store.list("videos")
        today = date.today().isoformat()
        upcoming = sorted((v for v in videos if v["planned_at"] and v["status"] != "gepostet"
                           and v["planned_at"][:10] >= today), key=lambda v: v["planned_at"])[:8]
        overdue = [v for v in videos if v["planned_at"] and v["status"] != "gepostet" and v["planned_at"][:10] < today]
        pipeline = {s: sum(1 for v in videos if v["status"] == s) for s in VIDEO_STATUS}
        posted = [v for v in videos if v["status"] == "gepostet"]
        measured = {m["video_id"] for m in self.store.list("metrics")}
        needs_metrics = [v for v in posted if v["id"] not in measured][:8]
        stats = analytics.overview(videos, self.store.list("metrics"))
        facts = self.store.list("facts")
        return {
            "countdown": gen.countdown(settings.get("release_date", "2026-11-19")),
            "settings": settings,
            "pipeline": pipeline,
            "upcoming": upcoming,
            "overdue": overdue,
            "needs_metrics": needs_metrics,
            "posted_today": sum(1 for v in posted if (v.get("posted_at") or "")[:10] == today),
            "posts_per_day": int(settings.get("posts_per_day", "2") or 2),
            "totals": stats["total"],
            "insights": stats["insights"][:4],
            "facts": {"total": len(facts), "unused": sum(1 for f in facts if not f["used_count"]),
                      "unverified": sum(1 for f in facts if f["status"] in ("geruecht", "leak", "spekulation"))},
        }

    def _facts(self, ids) -> list[dict]:
        out = []
        for i in ids or []:
            f = self.store.get("facts", int(i))
            if f:
                out.append(f)
        return out

    def _count_facts(self, ids) -> None:
        for f in self._facts(ids):
            self.store.update("facts", f["id"], {"used_count": f["used_count"] + 1})

    def generate(self, kind: str, body: dict):
        wpm = int(self.store.settings().get("voice_wpm", "150") or 150)
        if kind == "hooks":
            return gen.hook_options(str(body.get("topic", "")), limit=int(body.get("limit", 16)))
        facts = self._facts(body.get("fact_ids"))
        topic = str(body.get("topic", ""))
        series = str(body.get("series") or "Was keiner weiß")
        target = int(body.get("target_seconds") or 60)
        if kind == "script":
            res = gen.build_script(topic, facts, str(body.get("hook_type") or "keiner_bemerkt"), series, target,
                                   int(body.get("part") or 1), wpm)
            res["fact_ids"] = [f["id"] for f in facts]
            res["quality"] = gen.estimate_reach_score(res["hook"], res["seconds"],
                                                      bool(facts) and all(f["source_name"] or f["source_url"] for f in facts))
            return res
        if kind == "prompt":
            return {"prompt": gen.ai_prompt(topic, facts, series, target, self.store.settings().get("account_handle", ""))}
        if kind == "srt":
            return {"srt": gen.to_srt(str(body.get("script", "")), wpm)}
        if kind == "duration":
            text = str(body.get("script", ""))
            return {"seconds": gen.speech_seconds(text, wpm), "words": len(gen.words(text))}
        raise ApiError(404, "Unbekannter Generator")

    def plan(self, body: dict):
        s = self.store.settings()
        slots = gen.posting_plan(str(body.get("start") or date.today().isoformat()), int(body.get("days") or 7),
                                 int(body.get("posts_per_day") or s.get("posts_per_day", 2)),
                                 str(body.get("times") or s.get("post_times", "")))
        created = []
        if body.get("create"):
            for slot in slots:
                created.append(self.store.create("videos", {
                    "title": f"{slot['series']}: {slot['topic']}", "series": slot["series"],
                    "hook_type": slot["hook_type"], "hook": slot["hook"], "planned_at": slot["planned_at"],
                    "status": "idee"}))
        return {"slots": slots, "created": len(created)}

    def srt(self, video_id: str):
        v = self.store.get("videos", int(video_id)) if video_id.isdigit() else None
        if not v:
            raise ApiError(404, "Nicht gefunden")
        wpm = int(self.store.settings().get("voice_wpm", "150") or 150)
        return {"srt": gen.to_srt(v["script"], wpm), "filename": f"video-{v['id']}.srt"}

    def mark_posted(self, video_id: str, body: dict):
        if not video_id.isdigit() or not self.store.get("videos", int(video_id)):
            raise ApiError(404, "Nicht gefunden")
        return self.store.update("videos", int(video_id), {
            "status": "gepostet", "posted_at": str(body.get("posted_at") or datetime.now().replace(microsecond=0).isoformat()),
            "tiktok_url": str(body.get("tiktok_url") or "")})

    def import_metrics(self, body: dict):
        rows = analytics.parse_metrics_csv(str(body.get("csv", "")))
        hours = int(body.get("hours_after") or 24)
        videos = self.store.list("videos")
        by_title = {v["title"].strip().lower(): v for v in videos}
        imported, created = 0, 0
        for r in rows:
            title = (r.get("title") or "").strip()
            v = by_title.get(title.lower())
            if v is None:
                v = next((x for x in videos if title and (title.lower()[:40] in (x["caption"] or "").lower()
                                                          or title.lower()[:40] in x["title"].lower())), None)
            if v is None:
                if not body.get("create_missing") or not title:
                    continue
                v = self.store.create("videos", {"title": title[:200], "status": "gepostet",
                                                 "posted_at": r.get("posted_at", "")})
                by_title[title.lower()] = v
                videos.append(v)
                created += 1
            data = {k: r[k] for k in ("views", "likes", "comments", "shares", "saves", "avg_watch_seconds",
                                      "completion_pct", "followers_gained") if k in r}
            data["completion_pct"] = min(100.0, data.get("completion_pct", 0))
            self.store.create("metrics", {"video_id": v["id"], "hours_after": hours, **data})
            imported += 1
        return {"rows": len(rows), "imported": imported, "videos_created": created}


# ------------------------------------------------------------------ HTTP
def make_handler(studio: Studio, port: int):
    allowed_hosts = {f"{h}:{port}" for h in LOCAL_HOSTS}

    class Handler(BaseHTTPRequestHandler):
        server_version = "GTAStudio"
        sys_version = ""

        def log_message(self, fmt, *args):  # ruhig bleiben, nur Serverfehler zeigen
            if len(args) > 1 and str(args[1])[:1] == "5":
                super().log_message(fmt, *args)

        def _send(self, status: int, body: bytes, ctype: str, extra: list | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in SECURITY_HEADERS + list(extra or []):
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, data):
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _dispatch(self, method: str):
            if self.headers.get("Host", "") not in allowed_hosts:
                return self._json(421, {"error": "Falscher Host"})
            url = urlsplit(self.path)
            path = url.path
            if not path.startswith("/api/"):
                if method not in ("GET", "HEAD"):
                    return self._json(405, {"error": "Methode nicht erlaubt"})
                return self._static(path)
            if self.headers.get("X-Studio") != "1":
                return self._json(403, {"error": "Fehlender Header X-Studio"})
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc not in allowed_hosts:
                return self._json(403, {"error": "Fremde Herkunft"})
            body = None
            if method in ("POST", "PUT"):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = -1
                if length < 0 or length > MAX_BODY:
                    return self._json(413, {"error": "Anfrage zu groß"})
                if "application/json" not in (self.headers.get("Content-Type") or ""):
                    return self._json(415, {"error": "Nur JSON"})
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                except (ValueError, UnicodeDecodeError):
                    return self._json(400, {"error": "Ungültiges JSON"})
                if not isinstance(body, dict):
                    return self._json(400, {"error": "JSON-Objekt erwartet"})
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                return self._json(200, studio.handle(method, path, query, body))
            except ApiError as exc:
                return self._json(exc.status, {"error": exc.message})
            except (ValidationError, ValueError) as exc:
                return self._json(400, {"error": str(exc)})

        def _static(self, path: str):
            name = "index.html" if path in ("/", "/index.html") else (path[len("/static/"):] if path.startswith("/static/") else "")
            if not re.fullmatch(r"[a-z0-9_-]+\.(html|js|css|svg)", name):
                return self._send(404, b"Nicht gefunden", "text/plain; charset=utf-8")
            file = STATIC / name
            if not file.is_file():
                return self._send(404, b"Nicht gefunden", "text/plain; charset=utf-8")
            return self._send(200, file.read_bytes(), STATIC_TYPES[file.suffix])

        def do_GET(self):
            self._dispatch("GET")

        def do_HEAD(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_PUT(self):
            self._dispatch("PUT")

        def do_DELETE(self):
            self._dispatch("DELETE")

    return Handler


def serve(db_path: Path, port: int = 8777) -> None:
    from .seed import seed
    store = Store(db_path)
    added = seed(store)
    studio = Studio(store)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(studio, port))
    print(f"GTA TikTok Studio läuft: http://127.0.0.1:{port}")
    print(f"Daten: {db_path}" + (f"  ({added} Start-Fakten angelegt)" if added else ""))
    print("Beenden mit ctrl + C. Es wird nichts automatisch gepostet.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        httpd.server_close()
        store.close()
