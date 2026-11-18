"""Auswertung: Kennzahlen pro Video, Vergleich nach Serie und Hook-Typ, Konkurrenz-Ausreißer, CSV-Import."""
from __future__ import annotations

import csv
import io
import re
from statistics import median


def _rate(part: float, whole: float) -> float:
    return round(part / whole * 100, 2) if whole else 0.0


def video_kpis(m: dict, seconds: int = 60) -> dict:
    views = m.get("views", 0) or 0
    interactions = sum(m.get(k, 0) or 0 for k in ("likes", "comments", "shares", "saves"))
    avg = m.get("avg_watch_seconds", 0) or 0
    return {
        "views": views,
        "engagement_rate": _rate(interactions, views),
        "share_rate": _rate(m.get("shares", 0) or 0, views),
        "save_rate": _rate(m.get("saves", 0) or 0, views),
        "comment_rate": _rate(m.get("comments", 0) or 0, views),
        "watch_ratio": round(min(avg / seconds, 2) * 100, 1) if seconds else 0.0,
        "completion_pct": m.get("completion_pct", 0) or 0,
        "follow_rate": _rate(m.get("followers_gained", 0) or 0, views),
    }


def latest_metrics(metrics: list[dict]) -> dict[int, dict]:
    """Pro Video der jüngste Messpunkt (höchste Stundenzahl, dann neuester Eintrag)."""
    out: dict[int, dict] = {}
    for m in metrics:
        cur = out.get(m["video_id"])
        if cur is None or (m.get("hours_after", 0), m.get("id", 0)) > (cur.get("hours_after", 0), cur.get("id", 0)):
            out[m["video_id"]] = m
    return out


def overview(videos: list[dict], metrics: list[dict]) -> dict:
    latest = latest_metrics(metrics)
    rows = []
    for v in videos:
        m = latest.get(v["id"])
        if not m:
            continue
        k = video_kpis(m, v.get("target_seconds") or 60)
        rows.append({"id": v["id"], "title": v["title"], "series": v.get("series") or "–",
                     "hook_type": v.get("hook_type") or "–", "posted_at": v.get("posted_at", ""),
                     "hours_after": m.get("hours_after", 0), **k})
    views = [r["views"] for r in rows]
    med = median(views) if views else 0
    for r in rows:
        r["outlier"] = round(r["views"] / med, 2) if med else 0.0
    rows.sort(key=lambda r: r["views"], reverse=True)
    total = {
        "videos_measured": len(rows),
        "views": sum(views),
        "median_views": med,
        "followers_gained": sum((latest[r["id"]].get("followers_gained", 0) or 0) for r in rows),
        "avg_engagement": round(sum(r["engagement_rate"] for r in rows) / len(rows), 2) if rows else 0.0,
        "avg_completion": round(sum(r["completion_pct"] for r in rows) / len(rows), 1) if rows else 0.0,
    }
    return {"total": total, "videos": rows, "by_series": _group(rows, "series"),
            "by_hook": _group(rows, "hook_type"), "insights": insights(rows, med)}


def _group(rows: list[dict], key: str) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r[key], []).append(r)
    out = []
    for name, items in groups.items():
        out.append({
            "name": name, "videos": len(items),
            "median_views": median(i["views"] for i in items),
            "avg_engagement": round(sum(i["engagement_rate"] for i in items) / len(items), 2),
            "avg_completion": round(sum(i["completion_pct"] for i in items) / len(items), 1),
            "avg_share_rate": round(sum(i["share_rate"] for i in items) / len(items), 2),
        })
    out.sort(key=lambda g: g["median_views"], reverse=True)
    return out


def insights(rows: list[dict], med: float) -> list[str]:
    if not rows:
        return ["Noch keine Zahlen. Trag nach 24 Stunden die ersten Werte aus TikTok Studio ein."]
    tips = []
    if len(rows) < 5:
        tips.append(f"Erst {len(rows)} Videos gemessen. Ab etwa 10 Videos werden Muster belastbar.")
    best = rows[0]
    if best["outlier"] >= 2:
        tips.append(f"„{best['title']}“ hat {best['outlier']}× deinen Median. Mach 2–3 Folgevideos mit gleichem Hook-Typ ({best['hook_type']}).")
    low_completion = [r for r in rows if r["completion_pct"] and r["completion_pct"] < 25]
    if low_completion:
        tips.append(f"{len(low_completion)} Video(s) unter 25 % Wiedergabequote: Hook schneller, ersten Satz kürzen, früher den ersten Punkt bringen.")
    high_share = sorted(rows, key=lambda r: r["share_rate"], reverse=True)[0]
    if high_share["share_rate"] >= 1:
        tips.append(f"Teilen-Quote {high_share['share_rate']} % bei „{high_share['title']}“: dieses Thema verbreitet sich, mehr davon.")
    high_save = sorted(rows, key=lambda r: r["save_rate"], reverse=True)[0]
    if high_save["save_rate"] >= 1:
        tips.append(f"Viele Saves bei „{high_save['title']}“: Tipp- und Guide-Inhalte als feste Serie ausbauen.")
    by_hook = _group(rows, "hook_type")
    if len(by_hook) >= 2 and by_hook[-1]["videos"] >= 2:
        tips.append(f"Hook-Typ „{by_hook[-1]['name']}“ läuft am schwächsten. Seltener einsetzen.")
    return tips or ["Solide Werte. Bleib bei 1–3 Posts am Tag und teste jede Woche einen neuen Hook-Typ."]


def competitor_report(competitors: list[dict], posts: list[dict]) -> dict:
    by_comp: dict[int, list[dict]] = {}
    for p in posts:
        by_comp.setdefault(p["competitor_id"], []).append(p)
    comps, ranked = [], []
    for c in competitors:
        items = by_comp.get(c["id"], [])
        views = [p["views"] for p in items]
        med = median(views) if views else 0
        for p in items:
            score = round(p["views"] / med, 2) if med else 0.0
            er = _rate(sum(p.get(k, 0) or 0 for k in ("likes", "comments", "shares")), p["views"])
            ranked.append({**p, "handle": c["handle"], "outlier": score, "engagement_rate": er,
                           "views_per_follower": round(p["views"] / c["followers"], 2) if c.get("followers") else 0.0})
        comps.append({**c, "posts": len(items), "median_views": med,
                      "max_views": max(views) if views else 0})
    ranked.sort(key=lambda p: (p["outlier"], p["views"]), reverse=True)
    formats: dict[str, list[float]] = {}
    for p in ranked:
        formats.setdefault(p.get("format") or "–", []).append(p["outlier"])
    format_rank = sorted(({"format": k, "posts": len(v), "avg_outlier": round(sum(v) / len(v), 2)}
                          for k, v in formats.items()), key=lambda f: f["avg_outlier"], reverse=True)
    return {"competitors": comps, "top_posts": ranked[:25], "formats": format_rank}


# ---------------------------------------------------------------------------- CSV-Import
CSV_ALIASES = {
    "views": ("views", "video views", "aufrufe", "videoaufrufe", "wiedergaben"),
    "likes": ("likes", "gefällt mir", "gefaellt mir"),
    "comments": ("comments", "kommentare"),
    "shares": ("shares", "geteilt", "teilen", "mal geteilt"),
    "saves": ("saves", "favorites", "gespeichert", "favoriten"),
    "avg_watch_seconds": ("average watch time", "avg watch time", "durchschnittliche wiedergabezeit", "avg_watch_seconds"),
    "completion_pct": ("watched full video", "completion", "vollständig angesehen", "completion_pct"),
    "followers_gained": ("new followers", "neue follower", "followers_gained"),
    "title": ("title", "video title", "titel", "beschreibung", "caption"),
    "posted_at": ("date", "post time", "datum", "veröffentlicht", "posted_at"),
}


def _num(value: str) -> float:
    s = (value or "").strip().replace("%", "").replace("s", "").replace(" ", "")
    if not s:
        return 0.0
    mult = 1
    if s[-1:].upper() == "K":
        mult, s = 1000, s[:-1]
    elif s[-1:].upper() == "M":
        mult, s = 1_000_000, s[:-1]
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + ("." + tail if len(tail) != 3 else tail)
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def parse_metrics_csv(text: str) -> list[dict]:
    """Liest eine CSV (Export aus TikTok Studio oder eigene Tabelle). Erkennt deutsche und englische Spalten."""
    text = (text or "").lstrip("﻿")
    if not text.strip():
        return []
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    header_map = {}
    for col in reader.fieldnames or []:
        key = col.strip().lower()
        for target, aliases in CSV_ALIASES.items():
            if key in aliases and target not in header_map.values():
                header_map[col] = target
    rows = []
    for raw in reader:
        row = {}
        for col, target in header_map.items():
            val = raw.get(col, "")
            if target in ("title", "posted_at"):
                row[target] = (val or "").strip()
            else:
                n = _num(val)
                row[target] = n if target in ("avg_watch_seconds", "completion_pct") else int(n)
        if row.get("title") or row.get("views"):
            rows.append(row)
    return rows
