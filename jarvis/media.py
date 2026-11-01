"""Bilder (Stand 24): kostenlos über Cloudflare Workers AI (Modell FLUX.1 schnell).

- Gratis-Kontingent laut Cloudflare: 10.000 „Neuronen“ pro Tag ≈ 200 Bilder (512×512, 4 Schritte). JARVIS bleibt
  mit einem eigenen Tageslimit (Standard 30 Bilder) sicher darunter. Ohne Bezahlplan bei Cloudflare entstehen keine Kosten.
- Zugang: JARVIS_CLOUDFLARE_ACCOUNT (Konto-ID) und JARVIS_CLOUDFLARE_TOKEN (API-Token nur mit „Workers AI“-Recht)
  stehen in .env. Einrichten mit `python3 -m jarvis bilder-einrichten` (Eingabe verdeckt, nichts im Chat).
- Fester Endpunkt (api.cloudflare.com), TLS an, Zeitlimit, Größenlimit, keine Wiederholung. Der Bildtext geht vorher durch
  die Datenschutz-Schranke (Namen, Nummern, E-Mails werden geschwärzt).
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import ssl
import urllib.error
import urllib.request

ACCOUNT_ENV, TOKEN_ENV = "JARVIS_CLOUDFLARE_ACCOUNT", "JARVIS_CLOUDFLARE_TOKEN"
MODEL = "@cf/black-forest-labs/flux-1-schnell"
API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/" + MODEL
MAX_BYTES = 12_000_000
ACCOUNT_RE = re.compile(r"[0-9a-f]{32}")


class MediaError(RuntimeError):
    pass


def credentials(policy) -> tuple:
    get = lambda k: (getattr(policy, "_secrets", {}) or {}).get(k) or os.environ.get(k) or ""  # noqa: E731
    return get(ACCOUNT_ENV).strip(), get(TOKEN_ENV).strip()


def generate_image(prompt: str, account: str, token: str, steps: int = 6, opener=None) -> bytes:
    """Ein Bild erzeugen. Gibt die Bilddaten (JPEG/PNG) zurück."""
    if not ACCOUNT_RE.fullmatch(account or ""):
        raise MediaError("Cloudflare-Konto-ID fehlt oder ist ungültig (32 Zeichen, 0-9 und a-f).")
    if not token:
        raise MediaError("Cloudflare-Schlüssel fehlt.")
    body = json.dumps({"prompt": prompt[:2000], "steps": max(1, min(int(steps), 8))}).encode("utf-8")
    req = urllib.request.Request(API.format(account=account), data=body, method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    opener = opener or urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req, timeout=120) as resp:
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        hint = {401: "Schlüssel abgelehnt", 403: "Schlüssel hat kein Workers-AI-Recht", 429: "Tageskontingent erreicht"}
        raise MediaError(f"Cloudflare meldet Fehler {exc.code} ({hint.get(exc.code, 'bitte später erneut')}).") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise MediaError("Cloudflare ist gerade nicht erreichbar.") from None
    if len(raw) > MAX_BYTES:
        raise MediaError("Antwort zu groß – verworfen.")
    try:
        data = json.loads(raw.decode("utf-8"))
        img = base64.b64decode(data["result"]["image"], validate=True)
    except (ValueError, KeyError, TypeError, binascii.Error, UnicodeDecodeError):
        raise MediaError("Cloudflare hat kein Bild geliefert.") from None
    if not (img.startswith(b"\xff\xd8") or img.startswith(b"\x89PNG")):
        raise MediaError("Die Antwort ist kein Bild.")
    return img
