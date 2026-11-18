"""Tests für das GTA TikTok Studio – python3 -m unittest tests.test_gta_studio -v"""
import http.client
import json
import threading
import unittest
from datetime import datetime
from http.server import ThreadingHTTPServer

from gta_studio import analytics, generator as gen
from gta_studio.db import Store, ValidationError
from gta_studio.seed import FACTS, seed
from gta_studio.server import ApiError, Studio, make_handler


class GeneratorTests(unittest.TestCase):
    def test_speech_seconds(self):
        self.assertEqual(gen.speech_seconds(" ".join(["wort"] * 150), 150), 60.0)
        self.assertEqual(gen.words_for_seconds(60, 150), 150)

    def test_hooks_contain_topic(self):
        hooks = gen.hook_options("die Leonida Keys", limit=5)
        self.assertEqual(len(hooks), 5)
        self.assertTrue(all("Leonida Keys" in h["text"] for h in hooks))

    def test_script_marks_unconfirmed_facts(self):
        facts = [{"id": 1, "title": "Online-Modus", "detail": "Ein Online-Modus kommt.", "status": "geruecht",
                  "source_name": "", "source_url": ""}]
        s = gen.build_script("GTA Online", facts, "fakt_fake", "Fakt oder Fake", 60)
        self.assertIn("nicht offiziell bestätigt", s["script"])
        self.assertTrue(any("unbestätigte" in w for w in s["warnings"]))
        self.assertTrue(any("keine Quelle" in w for w in s["warnings"]))
        self.assertEqual(s["beats"][0]["label"], "Hook")
        self.assertGreater(s["beats"][-1]["end"], 0)

    def test_script_skips_disproven(self):
        facts = [{"id": 1, "title": "X", "detail": "falsch", "status": "widerlegt"}]
        s = gen.build_script("Thema", facts)
        self.assertNotIn("falsch", s["script"])

    def test_srt_format(self):
        srt = gen.to_srt("eins zwei drei vier fünf", 150, words_per_cue=4)
        self.assertTrue(srt.startswith("1\n00:00:00,000 --> 00:00:01,600\neins zwei drei vier"))
        self.assertIn("2\n00:00:01,600 --> 00:00:02,000\nfünf", srt)
        self.assertEqual(gen.to_srt(""), "")

    def test_plan(self):
        slots = gen.posting_plan("2026-11-19", days=3, posts_per_day=2, times="12:30,18:00")
        self.assertEqual(len(slots), 6)
        self.assertEqual(slots[0]["planned_at"], "2026-11-19T12:30")
        self.assertEqual(slots[0]["weekday"], "Do")
        self.assertEqual(len({s["series"] for s in slots}), len({s["series"] for s in slots}))
        self.assertTrue(all(s["series"] in gen.SERIES for s in gen.posting_plan("2026-11-19", 10, 3)))

    def test_countdown(self):
        self.assertFalse(gen.countdown("2026-11-19", datetime(2026, 11, 18, 12))["released"])
        self.assertEqual(gen.countdown("2026-11-19", datetime(2026, 11, 18, 12))["days"], 0)
        c = gen.countdown("2026-11-19", datetime(2026, 11, 21, 9))
        self.assertTrue(c["released"])
        self.assertEqual(c["label"], "Tag 3 nach Release")

    def test_ai_prompt_lists_status(self):
        p = gen.ai_prompt("Thema", [{"title": "A", "detail": "B", "status": "leak", "source_name": "Q"}], "Easter Eggs")
        self.assertIn("[Leak (nicht offiziell)] A: B (Quelle: Q)", p)
        self.assertIn("Nichts erfinden", p)


class AnalyticsTests(unittest.TestCase):
    def test_kpis(self):
        k = analytics.video_kpis({"views": 1000, "likes": 80, "comments": 10, "shares": 5, "saves": 5,
                                  "avg_watch_seconds": 30, "completion_pct": 40, "followers_gained": 10}, 60)
        self.assertEqual(k["engagement_rate"], 10.0)
        self.assertEqual(k["watch_ratio"], 50.0)
        self.assertEqual(k["follow_rate"], 1.0)
        self.assertEqual(analytics.video_kpis({"views": 0})["engagement_rate"], 0.0)

    def test_overview_uses_latest_and_outlier(self):
        videos = [{"id": 1, "title": "A", "series": "S1", "hook_type": "h1"},
                  {"id": 2, "title": "B", "series": "S2", "hook_type": "h2"},
                  {"id": 3, "title": "C", "series": "S1", "hook_type": "h1"}]
        metrics = [{"id": 1, "video_id": 1, "hours_after": 1, "views": 10},
                   {"id": 2, "video_id": 1, "hours_after": 24, "views": 9000, "shares": 200},
                   {"id": 3, "video_id": 2, "hours_after": 24, "views": 1000},
                   {"id": 4, "video_id": 3, "hours_after": 24, "views": 2000}]
        o = analytics.overview(videos, metrics)
        self.assertEqual(o["total"]["views"], 12000)
        self.assertEqual(o["videos"][0]["title"], "A")
        self.assertEqual(o["videos"][0]["outlier"], 4.5)
        self.assertEqual(o["by_series"][0]["name"], "S1")
        self.assertTrue(any("4.5×" in t for t in o["insights"]))

    def test_competitor_report(self):
        comps = [{"id": 1, "handle": "@a", "followers": 1000}]
        posts = [{"id": i, "competitor_id": 1, "title": f"P{i}", "views": v, "likes": 0, "comments": 0, "shares": 0,
                  "format": "News" if v < 5000 else "Leak-Analyse"} for i, v in enumerate([1000, 1000, 1200, 9000])]
        r = analytics.competitor_report(comps, posts)
        self.assertEqual(r["top_posts"][0]["title"], "P3")
        self.assertEqual(r["formats"][0]["format"], "Leak-Analyse")
        self.assertEqual(r["top_posts"][0]["views_per_follower"], 9.0)

    def test_csv_german(self):
        text = "Titel;Aufrufe;Likes;Kommentare;Geteilt;Gespeichert\nVideo A;12.345;1,2K;30;4;5\n"
        rows = analytics.parse_metrics_csv(text)
        self.assertEqual(rows[0]["title"], "Video A")
        self.assertEqual(rows[0]["views"], 12345)
        self.assertEqual(rows[0]["likes"], 1200)

    def test_csv_english(self):
        rows = analytics.parse_metrics_csv("Video title,Video views,Likes\nX,\"1,500\",20\n")
        self.assertEqual(rows[0]["views"], 1500)
        self.assertEqual(analytics.parse_metrics_csv(""), [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_seed_once(self):
        self.assertEqual(seed(self.store), len(FACTS))
        self.assertEqual(seed(self.store), 0)
        self.assertTrue(all(f["status"] in ("bestaetigt", "geruecht", "leak", "spekulation") for f in self.store.list("facts")))

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.store.create("facts", {"title": "x", "status": "quatsch"})
        with self.assertRaises(ValidationError):
            self.store.create("facts", {"title": "x", "source_url": "javascript:alert(1)"})
        with self.assertRaises(ValidationError):
            self.store.create("videos", {"title": ""})
        with self.assertRaises(ValidationError):
            self.store.create("metrics", {"video_id": 99})
        v = self.store.create("videos", {"title": "T"})
        with self.assertRaises(ValidationError):
            self.store.create("metrics", {"video_id": v["id"], "views": -1})

    def test_cascade_delete(self):
        v = self.store.create("videos", {"title": "T"})
        self.store.create("metrics", {"video_id": v["id"], "views": 5})
        self.store.delete("videos", v["id"])
        self.assertEqual(self.store.count("metrics"), 0)

    def test_settings_whitelist(self):
        s = self.store.set_settings({"account_handle": "@x", "evil": "1"})
        self.assertEqual(s["account_handle"], "@x")
        self.assertNotIn("evil", s)


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        seed(self.store)
        self.studio = Studio(self.store)

    def tearDown(self):
        self.store.close()

    def call(self, method, path, body=None, query=None):
        return self.studio.handle(method, path, query or {}, body)

    def test_full_flow(self):
        facts = self.call("GET", "/api/facts")
        script = self.call("POST", "/api/generate/script", {"topic": "Vice City", "fact_ids": [facts[0]["id"]]})
        self.assertIn(facts[0]["detail"], script["script"])
        v = self.call("POST", "/api/videos", {k: script[k] for k in ("title", "series", "hook", "hook_type", "script", "fact_ids")})
        self.assertEqual(self.store.get("facts", facts[0]["id"])["used_count"], 1)
        self.call("POST", f"/api/videos/{v['id']}/posted", {"tiktok_url": "https://www.tiktok.com/@x/video/1"})
        self.assertEqual(self.store.get("videos", v["id"])["status"], "gepostet")
        dash = self.call("GET", "/api/dashboard")
        self.assertEqual(dash["posted_today"], 1)
        self.assertEqual(len(dash["needs_metrics"]), 1)
        self.call("POST", "/api/metrics", {"video_id": v["id"], "views": 5000, "likes": 400})
        self.assertEqual(self.call("GET", "/api/analytics")["total"]["views"], 5000)
        self.assertIn("-->", self.call("GET", f"/api/videos/{v['id']}/srt")["srt"])

    def test_plan_create(self):
        r = self.call("POST", "/api/plan", {"start": "2026-11-19", "days": 2, "posts_per_day": 3, "create": True})
        self.assertEqual(r["created"], 6)
        self.assertEqual(len(self.call("GET", "/api/videos")), 6)
        self.assertEqual(len(self.call("GET", "/api/videos", query={"status": "idee"})), 6)

    def test_csv_import_matches_titles(self):
        self.call("POST", "/api/videos", {"title": "Mein Video"})
        r = self.call("POST", "/api/metrics/import", {"csv": "Titel,Aufrufe\nMein Video,100\nFremd,5\n"})
        self.assertEqual((r["rows"], r["imported"], r["videos_created"]), (2, 1, 0))
        r = self.call("POST", "/api/metrics/import", {"csv": "Titel,Aufrufe\nFremd,5\n", "create_missing": True})
        self.assertEqual(r["videos_created"], 1)

    def test_competitors(self):
        c = self.call("POST", "/api/competitors", {"handle": "@gta.de", "followers": 50000})
        self.call("POST", "/api/competitor-posts", {"competitor_id": c["id"], "title": "Leak", "views": 100000})
        rep = self.call("GET", "/api/competitors/report")
        self.assertEqual(rep["competitors"][0]["posts"], 1)
        with self.assertRaises(ValidationError):
            self.call("POST", "/api/competitors", {"handle": "@gta.de"})

    def test_errors(self):
        with self.assertRaises(ApiError):
            self.call("GET", "/api/unbekannt")
        with self.assertRaises(ApiError):
            self.call("DELETE", "/api/facts/99999")
        with self.assertRaises(ApiError):
            self.call("GET", "/api/videos/abc")


class HttpTests(unittest.TestCase):
    PORT = 18777

    @classmethod
    def setUpClass(cls):
        cls.store = Store(":memory:")
        seed(cls.store)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.PORT), make_handler(Studio(cls.store), cls.PORT))
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.store.close()

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.PORT, timeout=5)
        h = {"Host": f"127.0.0.1:{self.PORT}", "X-Studio": "1"}
        h.update(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        out = (r.status, dict(r.getheaders()), r.read())
        conn.close()
        return out

    def test_index_and_headers(self):
        status, headers, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"GTA TikTok Studio", body)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(self.req("GET", "/static/app.js")[0], 200)

    def test_path_traversal_blocked(self):
        self.assertEqual(self.req("GET", "/static/../server.py")[0], 404)
        self.assertEqual(self.req("GET", "/static/%2e%2e%2fdb.py")[0], 404)

    def test_wrong_host(self):
        self.assertEqual(self.req("GET", "/api/meta", headers={"Host": "evil.com"})[0], 421)

    def test_api_needs_header(self):
        self.assertEqual(self.req("GET", "/api/meta", headers={"X-Studio": "0"})[0], 403)
        self.assertEqual(self.req("GET", "/api/meta")[0], 200)

    def test_foreign_origin(self):
        self.assertEqual(self.req("POST", "/api/facts", {"title": "x"}, {"Origin": "https://evil.com"})[0], 403)

    def test_json_roundtrip_and_validation(self):
        status, _, body = self.req("POST", "/api/facts", {"title": "Neuer Fakt", "status": "leak"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "leak")
        self.assertEqual(self.req("POST", "/api/facts", {"title": "x", "status": "nope"})[0], 400)


if __name__ == "__main__":
    unittest.main()
