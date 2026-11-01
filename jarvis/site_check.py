"""Webseiten-Check (Stand 23): Wie modern ist die Webseite eines Betriebs? Nur lesen, nur öffentliche Seiten.

Sicherheit:
- Nur http/https, nur Standard-Ports (80/443), keine Zugangsdaten in der Adresse.
- Der Name wird aufgelöst und JEDE Adresse geprüft: kein localhost, kein Heimnetz (192.168…, 10…, 172.16–31…),
  kein Link-Local, kein Multicast. Weiterleitungen werden einzeln genauso geprüft (höchstens 4).
- Zeitlimit 10 s, höchstens 1,5 MB, keine Cookies, keine Formulare, kein JavaScript – es wird nur HTML gelesen.
- Ergebnis: Punkte 0–100 (100 = modern) und verständliche Befunde. Inhalte werden nicht gespeichert.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

TIMEOUT = 10
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 4
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) JARVIS-Webseiten-Check/1.0"


class SiteCheckError(ValueError):
    """Die Adresse darf oder kann nicht geprüft werden. Die Meldung ist für Noah verständlich."""


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise SiteCheckError("Keine Webseite angegeben.")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise SiteCheckError("Nur http- und https-Adressen werden geprüft.")
    if parts.username or parts.password or "@" in parts.netloc:
        raise SiteCheckError("Adressen mit Zugangsdaten werden nicht geprüft.")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or not re.fullmatch(r"[a-z0-9.-]{1,253}", host) or "." not in host:
        raise SiteCheckError("Das sieht nicht wie eine öffentliche Webseite aus.")
    if parts.port not in (None, 80, 443):
        raise SiteCheckError("Nur Webseiten auf den üblichen Ports werden geprüft.")
    if host == "localhost" or host.endswith((".local", ".lan", ".internal", ".home", ".localhost")):
        raise SiteCheckError("Geräte im eigenen Netz werden nicht geprüft.")
    return parts._replace(netloc=host if parts.port is None else f"{host}:{parts.port}", fragment="").geturl()


def _public_host(host: str) -> None:
    try:
        ipaddress.ip_address(host)
        raise SiteCheckError("Bitte die Webseiten-Adresse mit Namen angeben, nicht als IP-Nummer.")
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, OSError):
        raise SiteCheckError("Diese Webseite gibt es nicht (Name nicht gefunden).") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise SiteCheckError("Diese Adresse zeigt ins private Netz und wird nicht geprüft.")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # Weiterleitungen prüfen wir selbst
        return None


def fetch(url: str, resolver=_public_host) -> dict:
    """Lädt EINE öffentliche Seite. Gibt url (nach Weiterleitungen), status, html, sekunden, https zurück."""
    url = normalize_url(url)
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    started = time.monotonic()
    for _ in range(MAX_REDIRECTS + 1):
        resolver(urlsplit(url).hostname)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        try:
            resp = opener.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                url = normalize_url(urljoin(url, exc.headers["Location"]))
                continue
            raise SiteCheckError(f"Die Webseite antwortet mit Fehler {exc.code}.") from None
        except ssl.SSLError:
            raise SiteCheckError("Die Webseite hat ein ungültiges Sicherheitszertifikat.") from None
        except (urllib.error.URLError, OSError, ValueError):
            raise SiteCheckError("Die Webseite ist nicht erreichbar.") from None
        with resp:
            ctype = (resp.headers.get("content-type") or "").lower()
            raw = resp.read(MAX_BYTES + 1)
            status = resp.status
        if "html" not in ctype:
            raise SiteCheckError("Unter dieser Adresse liegt keine normale Webseite.")
        charset = re.search(r"charset=([\w-]+)", ctype)
        try:
            text = raw[:MAX_BYTES].decode(charset.group(1) if charset else "utf-8", "replace")
        except LookupError:
            text = raw[:MAX_BYTES].decode("utf-8", "replace")
        return {"url": url, "status": status, "html": text, "bytes": len(raw),
                "sekunden": round(time.monotonic() - started, 2), "https": url.startswith("https://")}
    raise SiteCheckError("Zu viele Weiterleitungen.")


def _meta(doc: str, name: str) -> str:
    m = re.search(r'<meta[^>]+(?:name|property)=["\']%s["\'][^>]*>' % re.escape(name), doc, re.I)
    if not m:
        return ""
    c = re.search(r'content=["\']([^"\']*)', m.group(0), re.I)
    return html.unescape(c.group(1)).strip()[:300] if c else ""


def analyze(page: dict, now_year: int | None = None) -> dict:
    """Bewertet das HTML. 100 = modern, unter 50 = deutlich veraltet."""
    doc = page.get("html") or ""
    low = doc.lower()
    year = now_year or time.localtime().tm_year
    findings, score = [], 100

    def minus(points: int, text: str):
        nonlocal score
        score -= points
        findings.append(text)

    title_m = re.search(r"<title[^>]*>(.*?)</title>", doc, re.I | re.S)
    title = html.unescape(re.sub(r"\s+", " ", title_m.group(1))).strip()[:120] if title_m else ""
    description = _meta(doc, "description")
    if not page.get("https"):
        minus(20, "Keine sichere Verbindung (kein https) – Browser zeigen „Nicht sicher“.")
    if 'name="viewport"' not in low and "name='viewport'" not in low:
        minus(20, "Nicht für Handys gebaut (keine mobile Ansicht).")
    if not title:
        minus(8, "Kein Seitentitel – schlecht für Google.")
    if not description:
        minus(8, "Keine Beschreibung für Google-Suchergebnisse.")
    if not _meta(doc, "og:title") and not _meta(doc, "og:image"):
        minus(4, "Keine Vorschau für WhatsApp/Instagram-Links.")
    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d{2})", low)]
    if years and max(years) < year - 2:
        minus(10, f"Stand im Fußbereich: {max(years)} – wirkt nicht gepflegt.")
    if re.search(r"<table[^>]*>.*?<table", low, re.S) or "<frameset" in low or "<font " in low or "<center>" in low:
        minus(12, "Veraltete Bautechnik (Tabellen-Layout, <font> oder Frames).")
    if ".swf" in low or "shockwave" in low:
        minus(15, "Nutzt Flash – funktioniert in keinem Browser mehr.")
    jq = re.search(r"jquery[-.]?(1\.\d+|2\.\d+)", low)
    if jq:
        minus(5, f"Alte Programm-Bibliothek (jQuery {jq.group(1)}).")
    if page.get("sekunden", 0) > 4:
        minus(8, f"Lädt langsam ({page['sekunden']} s).")
    if page.get("bytes", 0) > 1_200_000:
        minus(5, "Sehr große Seite – auf dem Handy langsam.")
    if not re.search(r"impressum", low):
        minus(6, "Kein Impressum-Link gefunden (Pflicht in Deutschland).")
    if not re.search(r"(datenschutz|privacy)", low):
        minus(4, "Kein Datenschutz-Link gefunden.")
    if not re.search(r"(reserv|termin|buch|bestell|kontakt)", low):
        minus(6, "Kein klarer Weg zu Reservierung, Termin oder Kontakt.")
    if "wix.com" in low or "jimdo" in low or "site123" in low:
        findings.append("Baukasten-Seite (Wix/Jimdo o. ä.) – oft schwer anpassbar.")
    score = max(0, min(100, score))
    grade = "modern" if score >= 75 else "ausbaufähig" if score >= 50 else "veraltet"
    return {"url": page.get("url", ""), "punkte": score, "urteil": grade, "befunde": findings or
            ["Keine groben Schwächen gefunden."], "titel": title, "beschreibung": description,
            "https": bool(page.get("https")), "sekunden": page.get("sekunden", 0)}


def check_site(url: str, fetcher=fetch) -> dict:
    """Prüft eine Webseite. Bei Problemen: punkte=None und eine verständliche Meldung."""
    try:
        return analyze(fetcher(url))
    except SiteCheckError as exc:
        return {"url": str(url)[:200], "punkte": None, "urteil": "nicht prüfbar", "befunde": [str(exc)],
                "titel": "", "beschreibung": "", "https": False, "sekunden": 0}
