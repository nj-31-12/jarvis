"""Anbindung an Claude (Anthropic) – nur Standardbibliothek, Python 3.8.

Sicherheitsregeln:
- Fester Endpunkt https://api.anthropic.com/v1/messages. Für Tests ist nur ein lokaler Fake-Server
  (http://127.0.0.1:…) erlaubt, kein anderer Host.
- TLS-Prüfung immer an. Zeitlimit. KEINE automatische Wiederholung (jede Anfrage kostet Geld).
- Antwortgröße begrenzt, nur JSON wird angenommen.
- Der Schlüssel kommt nur vom LLMRouter (aus .env) und wird nie gespeichert, protokolliert oder angezeigt.
- Fehlermeldungen enthalten nie Inhalte der Anfrage oder Antwort.

Kosten: Preise in US-Dollar je 1 Million Tokens (Stand 10/2026, vor jeder Freigabe beim Anbieter prüfen).
Umgerechnet wird bewusst 1 $ = 1 € – das überschätzt die Kosten leicht und ist damit auf der sicheren Seite.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
LOCAL_TEST_PREFIX = "http://127.0.0.1:"
TIMEOUT_SECONDS = 90
MAX_RESPONSE_BYTES = 1_000_000
USD_TO_EUR = 1.0                       # bewusst vorsichtig (überschätzt)

# Preise $ je 1 Mio. Tokens: (Eingabe, Ausgabe). Unbekanntes Modell → keine Anfrage (Preis nicht begrenzbar).
PRICES_USD_PER_MTOK = {
    "claude-haiku-5-5": (0.10, 0.50),     # gilt bis 100K Tokens Eingabe; JARVIS sendet höchstens ca. 12K Zeichen
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

# Höchstzahl Ausgabe-Tokens je Aufgabe (inkl. Denkschritte des Modells). Begrenzt die Kosten pro Anfrage.
MAX_OUTPUT_TOKENS = {"chat": 4096, "idea": 4096, "research": 6144, "briefing": 4096, "post": 2048, "skill": 2048,
                     "websuche": 4096, "webseite": 4096, "projekt": 16000, "bild": 400}
BUILD_TIMEOUT_SECONDS = 300            # ein ganzes Projekt zu schreiben dauert länger als eine Antwort

# Stand 23: Websuche (Server-Werkzeug von Claude). Preis laut Anbieter: 10 $ je 1.000 Suchen.
# Suchergebnisse werden als Eingabe-Tokens berechnet; je Suche rechnen wir vorsichtig mit bis zu 20.000 Tokens.
WEB_SEARCH_TOOL = "web_search_20250305"
WEB_SEARCH_USD = 0.01
WEB_SEARCH_TOKENS = 20_000

# Stand 18: Alltag mit „medium“ (gründlicher als „low“). Die Höchstkosten bleiben gleich, denn max_tokens begrenzt
# Antwort UND Denkschritte. Die Antwortprüfung läuft weiter mit „low“.
EFFORTS = ("low", "medium", "high")

TASK_HINTS = {
    "idea": "Bewerte die folgende Geschäftsidee strukturiert: Bewertungsraster, Beispielrechnung, nächste kleine "
            "Tests, Risiken (Recht, Nebentätigkeit, Kosten). Trenne Fakten, Schätzungen und Ideen.",
    "post": "Schreibe einen Social-Media-Entwurf zum folgenden Thema. Kennzeichne ihn als Entwurf. Keine "
            "Heilversprechen, Werbung korrekt kennzeichnen.",
    "research": "Fasse den Wissensstand zum folgenden Thema zusammen: Trends, Chancen, Risiken. Kennzeichne alles, "
                "was du nicht sicher weißt, als Schätzung. Erfinde keine Quellen.",
    "briefing": "Erstelle ein kurzes, klares Briefing aus den folgenden Angaben.",
    "skill": "Bearbeite die folgende Aufgabe knapp und sachlich.",
    "webseite": "Du bist Texter und Webdesigner. Antworte NUR mit einem JSON-Objekt (ohne Erklärung, ohne "
                "Markdown) im verlangten Format. Erfinde keine Preise, Auszeichnungen, Bewertungen oder Kontaktdaten.",
    "projekt": "Du bist ein Weltklasse-Entwickler und Designer. Baue das Gewünschte als EINE vollständige, sofort "
               "lauffähige HTML-Datei (HTML, CSS und JavaScript in dieser einen Datei). Modernes, hochwertiges Design, "
               "Animationen (gern 3D mit Canvas/WebGL), Handy-Ansicht, Deutsch. Keine Platzhalter-Funktionen: alles soll "
               "wirklich funktionieren. Keine Daten an fremde Server senden, keine Tracker, keine Formulare an externe "
               "Adressen. Antworte NUR mit der HTML-Datei, beginnend mit <!doctype html>.",
    "bild": "Formuliere aus der Bildbeschreibung einen präzisen englischen Prompt für ein Bildmodell (FLUX): Motiv, "
            "Stil, Licht, Perspektive, Details. Höchstens 70 Wörter. Antworte NUR mit dem Prompt.",
    "websuche": "Du recherchierst im Internet. Nutze die Websuche. Antworte am Ende NUR mit dem verlangten JSON. "
                "Nur öffentlich sichtbare Firmenangaben (Name, Ort, Webseite) – keine Privatpersonen, keine "
                "E-Mail-Adressen, keine Telefonnummern.",
}


class AIServiceError(RuntimeError):
    """Der KI-Dienst hat nicht wie erwartet geantwortet. Die Meldung enthält nie Inhalte.

    not_billed=True heißt: Die Anfrage kann keine Kosten verursacht haben (abgelehnt oder nicht angekommen)."""

    def __init__(self, message: str, not_billed: bool = False):
        super().__init__(message)
        self.not_billed = not_billed


def _check_endpoint(endpoint: str) -> str:
    if endpoint == API_URL:
        return endpoint
    if endpoint.startswith(LOCAL_TEST_PREFIX) and "@" not in endpoint:
        return endpoint
    raise AIServiceError("Unerlaubter Endpunkt für Claude. Es wurde nichts gesendet.")


def to_messages(history: list, text: str) -> list:
    """JARVIS-Verlauf (du/jarvis) → Claude-Format (user/assistant). Beginnt immer mit user, wechselt sich ab."""
    messages = []
    for item in list(history) + [{"role": "du", "text": text}]:
        role = "user" if item.get("role") == "du" else "assistant" if item.get("role") == "jarvis" else None
        content = str(item.get("text") or "").strip()
        if role is None or not content:
            continue
        if not messages and role == "assistant":
            continue                                   # Gespräch muss mit Noahs Nachricht beginnen
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + content
        else:
            messages.append({"role": role, "content": content})
    if not messages or messages[-1]["role"] != "user":
        raise AIServiceError("Leere Nachricht. Es wurde nichts gesendet.")
    return messages


class AnthropicModel:
    """Claude als Gehirn. Wird nur über LLMRouter benutzt (Methoden *_billed mit Schlüssel)."""
    is_test_mode = False
    provider = "anthropic"

    def __init__(self, name: str, endpoint: str = API_URL, timeout: float = TIMEOUT_SECONDS):
        if name not in PRICES_USD_PER_MTOK:
            raise AIServiceError(f"Für '{str(name)[:64]}' ist kein Preis hinterlegt. Ohne Preis keine Anfrage.")
        self.name = name
        self.endpoint = _check_endpoint(endpoint)
        self.timeout = float(timeout)
        self.cost_per_call_eur = 0.0       # die Reservierung kommt aus der Konfiguration (cost_per_call_eur)

    # ------------------------------------------------------------------ Kosten
    def max_cost_eur(self, task: str, chars: int, searches: int = 0) -> float:
        """Höchstmögliche Kosten einer Anfrage: Zeichen (≥ Tokens) × Eingabepreis + max. Ausgabe × Ausgabepreis.
        Mit Websuche zusätzlich: je Suche Gebühr + vorsichtig geschätzte Ergebnis-Tokens."""
        price_in, price_out = PRICES_USD_PER_MTOK[self.name]
        out_tokens = MAX_OUTPUT_TOKENS.get(task, 2048)
        searches = max(int(searches), 0)
        usd = ((max(int(chars), 0) + searches * WEB_SEARCH_TOKENS) * price_in + out_tokens * price_out) / 1_000_000
        return (usd + searches * WEB_SEARCH_USD) * USD_TO_EUR

    def actual_cost_eur(self, usage: dict) -> float | None:
        """Tatsächliche Kosten aus der Antwort. None, wenn keine verwertbare Angabe vorliegt."""
        if not isinstance(usage, dict):
            return None
        price_in, price_out = PRICES_USD_PER_MTOK[self.name]
        try:
            tin = int(usage.get("input_tokens") or 0)
            tin += int(usage.get("cache_creation_input_tokens") or 0) * 1.25
            tin += int(usage.get("cache_read_input_tokens") or 0) * 0.1
            tout = int(usage["output_tokens"])
            stu = usage.get("server_tool_use") if isinstance(usage.get("server_tool_use"), dict) else {}
            searches = int(stu.get("web_search_requests") or 0)
        except (KeyError, TypeError, ValueError):
            return None
        return ((tin * price_in + tout * price_out) / 1_000_000 + searches * WEB_SEARCH_USD) * USD_TO_EUR

    # ------------------------------------------------------------------ Aufrufe (nur über LLMRouter)
    def chat(self, *_a, **_k):
        raise AIServiceError("Claude darf nur über die Sicherheitskette (LLMRouter) aufgerufen werden.")

    complete = chat

    def chat_billed(self, system_prompt: str, history: list, text: str, api_key: str, effort: str = "medium",
                    search: int = 0):
        body = {"model": self.name, "max_tokens": MAX_OUTPUT_TOKENS["chat"],
                "system": system_prompt or "", "messages": to_messages(history, text),
                "output_config": {"effort": effort if effort in EFFORTS else "medium"}}
        if search:                         # Stand 24: Claude entscheidet selbst, ob er im Internet nachsieht
            body["tools"] = [_search_tool(search)]
        return self._send(body, api_key)

    def build_billed(self, text: str, api_key: str):
        """Stand 24: ein ganzes Projekt (eine HTML-Datei) schreiben."""
        body = {"model": self.name, "max_tokens": MAX_OUTPUT_TOKENS["projekt"],
                "system": TASK_HINTS["projekt"], "messages": to_messages([], text), "output_config": {"effort": "medium"}}
        return self._send(body, api_key, timeout=BUILD_TIMEOUT_SECONDS)

    def complete_billed(self, task: str, text: str, api_key: str):
        hint = TASK_HINTS.get(task, TASK_HINTS["skill"])
        body = {"model": self.name, "max_tokens": MAX_OUTPUT_TOKENS.get(task, 2048),
                "system": "Du bist JARVIS, Noahs persönlicher Assistent. Antworte auf Deutsch. " + hint,
                "messages": to_messages([], text), "output_config": {"effort": "low"}}
        return self._send(body, api_key)

    def search_billed(self, text: str, api_key: str, max_uses: int = 5):
        """Stand 23: Recherche mit Websuche (Server-Werkzeug). Höchstens max_uses Suchen, Standort Deutschland."""
        body = {"model": self.name, "max_tokens": MAX_OUTPUT_TOKENS["websuche"],
                "system": "Du bist JARVIS, Noahs Recherche-Assistent. Antworte auf Deutsch. " + TASK_HINTS["websuche"],
                "messages": to_messages([], text), "output_config": {"effort": "low"},
                "tools": [_search_tool(max_uses)]}
        return self._send(body, api_key)

    def _send(self, body: dict, api_key: str, timeout: float | None = None):
        """Eine Anfrage, keine Wiederholung. Gibt (Antworttext, tatsächliche Kosten in € oder None) zurück."""
        if not api_key:
            raise AIServiceError("Schlüssel fehlt. Es wurde nichts gesendet.")
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=data, method="POST", headers={
            "content-type": "application/json", "x-api-key": api_key, "anthropic-version": API_VERSION})
        if self.endpoint == API_URL:
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        else:   # lokaler Fake-Server im Test: nie über einen Proxy
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=timeout or self.timeout) as resp:
                ctype = resp.headers.get("content-type", "")
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise AIServiceError(_http_error_text(exc.code), not_billed=400 <= exc.code < 500) from None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            timeout = "timed out" in str(exc).lower()
            reason = "Zeitüberschreitung" if timeout else "keine Verbindung"
            raise AIServiceError(f"Claude ist gerade nicht erreichbar ({reason}).", not_billed=not timeout) from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AIServiceError("Antwort von Claude ist ungewöhnlich groß und wurde verworfen.")
        if "application/json" not in ctype.lower():
            raise AIServiceError("Antwort von Claude hat ein unerwartetes Format und wurde verworfen.")
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise AIServiceError("Antwort von Claude war nicht lesbar.") from None
        return self._parse(msg)

    def _parse(self, msg):
        if not isinstance(msg, dict):
            raise AIServiceError("Antwort von Claude war nicht lesbar.")
        cost = self.actual_cost_eur(msg.get("usage"))
        stop = msg.get("stop_reason")
        blocks = msg.get("content") if isinstance(msg.get("content"), list) else []
        texts = [b for b in blocks if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        cited = any(b.get("citations") for b in texts)
        # Mit Websuche liefert Claude den Text in vielen Stücken (je Quelle eins) – die gehören direkt aneinander.
        text = ("" if cited else "\n\n").join(b["text"] for b in texts).strip()
        links = []
        for b in texts:
            for c in b.get("citations") or []:
                url, title = (c.get("url"), c.get("title")) if isinstance(c, dict) else (None, None)
                if isinstance(url, str) and url.startswith("https://") and url not in [u for u, _ in links] and len(links) < 5:
                    links.append((url, re.sub(r"[\[\]\n]", " ", str(title or url))[:80]))
        if text and links:
            text += "\n\n🌐 Quellen: " + " · ".join(f"[{t}]({u})" for u, t in links)
        if stop == "refusal":
            return ("Dazu kann ich keine Antwort geben (Claude hat die Anfrage aus Sicherheitsgründen abgelehnt). "
                    "Formuliere die Frage gern anders.", cost)
        if not text:
            if stop == "pause_turn":
                return ("Die Recherche wurde nach vielen Suchschritten angehalten und ist unvollständig.", cost)
            if stop == "max_tokens":
                return ("Meine Antwort wurde zu lang und abgeschnitten. Stell die Frage bitte etwas enger.", cost)
            raise AIServiceError("Claude hat keine Textantwort geliefert.")
        if stop == "max_tokens":
            text += "\n\n_(Antwort wegen Längenbegrenzung abgeschnitten.)_"
        return text, cost


def _search_tool(max_uses: int) -> dict:
    return {"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": max(1, min(int(max_uses), 10)),
            "user_location": {"type": "approximate", "country": "DE", "timezone": "Europe/Berlin"}}


def _http_error_text(code: int) -> str:
    if code == 401:
        return "Claude hat den Schlüssel abgelehnt (401). Bitte den Schlüssel in .env prüfen."
    if code == 403:
        return "Claude verweigert den Zugriff (403). Bitte Konto und Berechtigungen prüfen."
    if code == 429:
        return "Claude meldet zu viele Anfragen oder ein erreichtes Limit (429). Bitte später erneut versuchen."
    if code == 400:
        return "Claude hat die Anfrage als ungültig abgelehnt (400)."
    if code in (402,) or code == 413:
        return f"Claude hat die Anfrage abgelehnt ({code}). Guthaben oder Größe prüfen."
    if 500 <= code < 600:
        return f"Claude hat gerade technische Probleme ({code}). Bitte später erneut versuchen."
    return f"Claude hat mit Fehler {code} geantwortet."
