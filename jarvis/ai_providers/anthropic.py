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
MAX_OUTPUT_TOKENS = {"chat": 4096, "idea": 4096, "research": 6144, "briefing": 4096, "post": 2048, "skill": 2048}

TASK_HINTS = {
    "idea": "Bewerte die folgende Geschäftsidee strukturiert: Bewertungsraster, Beispielrechnung, nächste kleine "
            "Tests, Risiken (Recht, Nebentätigkeit, Kosten). Trenne Fakten, Schätzungen und Ideen.",
    "post": "Schreibe einen Social-Media-Entwurf zum folgenden Thema. Kennzeichne ihn als Entwurf. Keine "
            "Heilversprechen, Werbung korrekt kennzeichnen.",
    "research": "Fasse den Wissensstand zum folgenden Thema zusammen: Trends, Chancen, Risiken. Kennzeichne alles, "
                "was du nicht sicher weißt, als Schätzung. Erfinde keine Quellen.",
    "briefing": "Erstelle ein kurzes, klares Briefing aus den folgenden Angaben.",
    "skill": "Bearbeite die folgende Aufgabe knapp und sachlich.",
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
    def max_cost_eur(self, task: str, chars: int) -> float:
        """Höchstmögliche Kosten einer Anfrage: Zeichen (≥ Tokens) × Eingabepreis + max. Ausgabe × Ausgabepreis."""
        price_in, price_out = PRICES_USD_PER_MTOK[self.name]
        out_tokens = MAX_OUTPUT_TOKENS.get(task, 2048)
        usd = (max(int(chars), 0) * price_in + out_tokens * price_out) / 1_000_000
        return usd * USD_TO_EUR

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
        except (KeyError, TypeError, ValueError):
            return None
        return (tin * price_in + tout * price_out) / 1_000_000 * USD_TO_EUR

    # ------------------------------------------------------------------ Aufrufe (nur über LLMRouter)
    def chat(self, *_a, **_k):
        raise AIServiceError("Claude darf nur über die Sicherheitskette (LLMRouter) aufgerufen werden.")

    complete = chat

    def chat_billed(self, system_prompt: str, history: list, text: str, api_key: str):
        body = {"model": self.name, "max_tokens": MAX_OUTPUT_TOKENS["chat"],
                "system": system_prompt or "", "messages": to_messages(history, text),
                "output_config": {"effort": "low"}}
        return self._send(body, api_key)

    def complete_billed(self, task: str, text: str, api_key: str):
        hint = TASK_HINTS.get(task, TASK_HINTS["skill"])
        body = {"model": self.name, "max_tokens": MAX_OUTPUT_TOKENS.get(task, 2048),
                "system": "Du bist JARVIS, Noahs persönlicher Assistent. Antworte auf Deutsch. " + hint,
                "messages": to_messages([], text), "output_config": {"effort": "low"}}
        return self._send(body, api_key)

    def _send(self, body: dict, api_key: str):
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
            with opener.open(req, timeout=self.timeout) as resp:
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
        text = "\n\n".join(b.get("text", "") for b in blocks
                           if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
        text = text.strip()
        if stop == "refusal":
            return ("Dazu kann ich keine Antwort geben (Claude hat die Anfrage aus Sicherheitsgründen abgelehnt). "
                    "Formuliere die Frage gern anders.", cost)
        if not text:
            if stop == "max_tokens":
                return ("Meine Antwort wurde zu lang und abgeschnitten. Stell die Frage bitte etwas enger.", cost)
            raise AIServiceError("Claude hat keine Textantwort geliefert.")
        if stop == "max_tokens":
            text += "\n\n_(Antwort wegen Längenbegrenzung abgeschnitten.)_"
        return text, cost


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
