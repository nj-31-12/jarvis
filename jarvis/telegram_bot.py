"""Telegram-Anbindung (Testmodus) – nur Python-Standardbibliothek, keine Installation.

Sicherheitsregeln:
  - Startet nur, wenn TELEGRAM_BOT_TOKEN und mindestens eine erlaubte Benutzer-ID gesetzt sind.
  - Nachrichten von fremden Benutzern werden ignoriert und protokolliert.
  - Nur private Chats (keine Gruppen).
  - Freigabe-Buttons werden in approval.py geprüft (Benutzer-ID, Chat, Signatur, Ablaufzeit, einmalig).
Der Token wird niemals ausgegeben oder protokolliert.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .config import load_config, load_secrets
from .core import Jarvis

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramAPI:
    def __init__(self, token: str):
        self._token = token

    def call(self, method: str, http_timeout: int = 40, **params):
        req = urllib.request.Request(
            API.format(token=self._token, method=method),
            data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=http_timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # Token nicht in Fehlermeldung ausgeben
            raise RuntimeError(f"Telegram-Fehler {exc.code} bei {method}") from None
        if not body.get("ok"):
            raise RuntimeError(f"Telegram-Fehler bei {method}: {body.get('description')}")
        return body["result"]


def make_channel(api: TelegramAPI, chat_id: int):
    def send(text: str, silent: bool, buttons):
        params = {"chat_id": chat_id, "text": text[:4000], "disable_notification": silent}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": [
                [{"text": label, "callback_data": data} for label, data in row] for row in buttons]}
        api.call("sendMessage", **params)
    return send


def run() -> None:
    cfg, sec = load_config(), load_secrets()
    token = sec.get("TELEGRAM_BOT_TOKEN")
    allowed = [int(u) for u in cfg["telegram"]["allowed_user_ids"]]
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN fehlt in .env – siehe docs/06_Telegram_Sicherheit.md")
    if not allowed:
        raise SystemExit("telegram.allowed_user_ids ist leer – ohne Whitelist startet der Bot nicht.")
    if not sec.get("JARVIS_APPROVAL_SECRET"):
        raise SystemExit("JARVIS_APPROVAL_SECRET fehlt in .env – siehe docs/06_Telegram_Sicherheit.md")
    chat_id = int(cfg["telegram"].get("approval_chat_id") or allowed[0])
    cfg["telegram"]["approval_chat_id"] = chat_id
    api = TelegramAPI(token)
    jarvis = Jarvis(cfg, sec, channel=make_channel(api, chat_id))
    me = api.call("getMe")
    print(f"JARVIS-Testbot @{me['username']} läuft. Beenden mit Strg+C.")
    jarvis.audit.write("telegram_start", bot=me["username"])
    offset = 0
    while True:
        try:
            updates = api.call("getUpdates", http_timeout=40, offset=offset, timeout=30,
                               allowed_updates=["message", "callback_query"])
        except Exception as exc:  # noqa: BLE001
            print("Verbindungsproblem:", exc)
            time.sleep(5)
            continue
        for upd in updates:
            offset = upd["update_id"] + 1
            try:
                _handle_update(api, jarvis, upd, allowed, chat_id)
            except Exception as exc:  # noqa: BLE001
                jarvis.audit.write("error", error=str(exc))
                print("Fehler:", exc)


def _handle_update(api: TelegramAPI, jarvis: Jarvis, upd: dict, allowed: list[int], chat_id: int) -> None:
    if "callback_query" in upd:
        cq = upd["callback_query"]
        user = cq["from"]["id"]
        cq_chat = cq.get("message", {}).get("chat", {}).get("id")
        answer = jarvis.on_button(cq.get("data", ""), user, cq_chat)
        api.call("answerCallbackQuery", callback_query_id=cq["id"], text=answer[:190])
        if user in allowed:
            api.call("sendMessage", chat_id=chat_id, text=answer)
        return
    msg = upd.get("message") or {}
    user = msg.get("from", {}).get("id")
    chat = msg.get("chat", {})
    if user not in allowed or chat.get("type") != "private":
        jarvis.audit.write("ignored_message", user=user, chat_type=chat.get("type"))
        return
    if "voice" in msg:
        reply = jarvis.handle_voice(msg["voice"].get("duration", 0))
    else:
        reply = jarvis.handle_text(msg.get("text", ""))
    api.call("sendMessage", chat_id=chat["id"], text=reply[:4000])
