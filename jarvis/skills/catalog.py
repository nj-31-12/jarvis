"""Die sechs Skills von JARVIS mit ihren sicheren Adaptern (Version 5, Phase C).

Alle Adapter hier:
  - verbinden KEIN Konto (connects_account = False),
  - benutzen KEIN Netzwerk (uses_network = False; die Tests prüfen das zusätzlich),
  - arbeiten mit erfundenen Testdaten. Ausnahme „Wissen“: liest data/vault (nur nicht vertrauliche Notizen)
    und schreibt nur neue Notizen in 00_Inbox/JARVIS – genau wie bisher.
Echte Adapter (Gmail, Google Kalender, Shopify, Websuche) kommen erst nach deiner ausdrücklichen Freigabe.
"""
from __future__ import annotations

import datetime as dt
import re

from .base import Operation, SkillBlocked, SkillError, SkillResult, SkillSpec

EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}")
TEST_LABEL = "TESTDATEN (erfunden, kein echtes Konto)"


class _Adapter:
    connects_account = False
    uses_network = False
    label = "Testadapter mit erfundenen Daten"

    def __init__(self, ctx):
        self.ctx = ctx

    @staticmethod
    def _text(value, name: str, max_len: int = 500, required: bool = True) -> str:
        value = str(value or "").strip()
        if required and not value:
            raise SkillError(f"Bitte {name} angeben.")
        if len(value) > max_len:
            raise SkillError(f"{name} ist zu lang (höchstens {max_len} Zeichen).")
        return value


# ---------------------------------------------------------------------- Internetrecherche
class ResearchTestAdapter(_Adapter):
    SOURCES = [
        ("Shopify", "Shopify-Hilfeseiten: Produktseiten mit klaren Nutzenversprechen und Bewertungen verkaufen besser.",
         "https://help.shopify.example/produkte"),
        ("Fitness", "Studienübersicht (Beispiel): 1,6 g Protein pro kg Körpergewicht gilt als sinnvolle Obergrenze.",
         "https://studien.example/protein"),
        ("Affiliate", "Affiliate-Grundlagen: Werbekennzeichnung „Anzeige“ ist in Deutschland Pflicht.",
         "https://recht.example/kennzeichnung"),
        ("KI", "KI-Automatisierung: Kleine Shops starten meist mit automatischen Antworten auf Standardfragen.",
         "https://ki.example/automatisierung"),
    ]

    def search(self, query: str = "") -> SkillResult:
        q = self._text(query, "einen Suchbegriff", 200).lower()
        hits = [(t, s, u) for t, s, u in self.SOURCES if t.lower() in q or any(w in s.lower() for w in q.split())]
        hits = hits[:3] or self.SOURCES[:1]
        lines = [f"🔎 Recherche „{query}“ – {TEST_LABEL}", ""]
        lines += [f"- {s} (Quelle: {u})" for _, s, u in hits]
        lines += ["", "Hinweis: Echte Websuche mit überprüfbaren Quellen kommt erst nach deiner Freigabe."]
        return SkillResult("research", "search", "\n".join(lines), [{"quelle": u, "text": s} for _, s, u in hits])


# ---------------------------------------------------------------------- Gmail
class MailTestAdapter(_Adapter):
    INBOX = [
        {"id": "m1", "von": "kunde@example.com", "betreff": "Frage zum Coaching-Paket", "text": "Hallo Noah, was kostet das 12-Wochen-Paket?", "ungelesen": True},
        {"id": "m2", "von": "partner@example.org", "betreff": "Kooperation Duftproben", "text": "Wir hätten Interesse an einer Kooperation.", "ungelesen": True},
        {"id": "m3", "von": "newsletter@example.net", "betreff": "Wochenrückblick", "text": "Die wichtigsten News der Woche.", "ungelesen": False},
    ]

    def list_unread(self) -> SkillResult:
        mails = [m for m in self.INBOX if m["ungelesen"]]
        lines = [f"📬 {len(mails)} ungelesene E-Mails – {TEST_LABEL}", ""]
        lines += [f"- {m['id']}: {m['betreff']} (von {m['von']})" for m in mails]
        return SkillResult("gmail", "list_unread", "\n".join(lines),
                           [{"id": m["id"], "betreff": m["betreff"], "von": m["von"]} for m in mails])

    def draft_reply(self, message_id: str = "", text: str = "") -> SkillResult:
        mail = next((m for m in self.INBOX if m["id"] == message_id), None)
        if mail is None:
            raise SkillError("Diese E-Mail gibt es nicht.")
        body = self._text(text, "einen Antworttext", 4000)
        draft = f"An: {mail['von']}\nBetreff: Re: {mail['betreff']}\n\n{body}"
        return SkillResult("gmail", "draft_reply", "✍️ Entwurf (nicht gesendet):\n\n" + draft,
                           [{"an": mail["von"], "betreff": "Re: " + mail["betreff"]}])

    def propose_send(self, to: str = "", subject: str = "", text: str = "") -> SkillResult:
        to = self._text(to, "einen Empfänger", 254)
        if not EMAIL.fullmatch(to):
            raise SkillError("Die Empfängeradresse ist ungültig.")
        subject = self._text(subject, "einen Betreff", 200)
        text = self._text(text, "einen Text", 4000)
        a = self.ctx.gate.propose("send_email", {"an": to, "betreff": subject, "text": text},
                                  reason="Vorschlag des Skills Gmail",
                                  meta={"beschreibung": f"E-Mail an {to} senden.",
                                        "konten": ["Gmail (Testadapter – Ausführung nur simuliert)"],
                                        "daten": [f"Empfänger: {to}", f"Betreff: {subject}", f"Text ({len(text)} Zeichen)"],
                                        "kosten_eur": 0, "quelle": "Skill gmail"})
        return SkillResult("gmail", "propose_send", f"📧 Versand vorgeschlagen. Freigabe #{a.id} wartet in der "
                                                    f"Freigabezentrale.", proposal_id=a.id)


# ---------------------------------------------------------------------- Kalender
class CalendarTestAdapter(_Adapter):
    def _events(self):
        today = dt.date.today()
        return [
            {"datum": today, "zeit": "07:30", "titel": "Berufsschule"},
            {"datum": today, "zeit": "18:00", "titel": "Training Oberkörper"},
            {"datum": today + dt.timedelta(days=1), "zeit": "09:00", "titel": "Autohaus: Fahrzeugübergabe"},
            {"datum": today + dt.timedelta(days=3), "zeit": "19:30", "titel": "Coaching-Call (Beispiel)"},
        ]

    def list_today(self) -> SkillResult:
        ev = [e for e in self._events() if e["datum"] == dt.date.today()]
        lines = [f"📅 Heute – {TEST_LABEL}", ""] + [f"- {e['zeit']} {e['titel']}" for e in ev]
        return SkillResult("calendar", "list_today", "\n".join(lines),
                           [{"zeit": e["zeit"], "titel": e["titel"]} for e in ev])

    def list_week(self) -> SkillResult:
        ev = [e for e in self._events() if 0 <= (e["datum"] - dt.date.today()).days < 7]
        lines = [f"📅 Nächste 7 Tage – {TEST_LABEL}", ""]
        lines += [f"- {e['datum'].strftime('%d.%m.')} {e['zeit']} {e['titel']}" for e in ev]
        return SkillResult("calendar", "list_week", "\n".join(lines),
                           [{"datum": e["datum"].isoformat(), "zeit": e["zeit"], "titel": e["titel"]} for e in ev])

    def propose_event(self, title: str = "", date: str = "", time: str = "") -> SkillResult:
        title = self._text(title, "einen Titel", 120)
        try:
            day = dt.date.fromisoformat(self._text(date, "ein Datum (JJJJ-MM-TT)", 10))
        except ValueError:
            raise SkillError("Datum bitte als JJJJ-MM-TT angeben.") from None
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(time)):
            raise SkillError("Uhrzeit bitte als HH:MM angeben.")
        a = self.ctx.gate.propose("calendar_write", {"titel": title, "datum": day.isoformat(), "uhrzeit": time},
                                  reason="Vorschlag des Skills Kalender",
                                  meta={"beschreibung": f"Termin „{title}“ am {day.strftime('%d.%m.%Y')} um {time} eintragen.",
                                        "konten": ["Kalender (Testadapter – Ausführung nur simuliert)"],
                                        "daten": [f"Titel: {title}", f"Datum: {day.isoformat()}", f"Uhrzeit: {time}"],
                                        "kosten_eur": 0, "quelle": "Skill calendar"})
        return SkillResult("calendar", "propose_event", f"📅 Termin vorgeschlagen. Freigabe #{a.id} wartet.",
                           proposal_id=a.id)


# ---------------------------------------------------------------------- Shopify
class ShopTestAdapter(_Adapter):
    PRODUCTS = {
        "p1": {"titel": "Protein-Guide (E-Book)", "preis": 24.0, "bestand": None},
        "p2": {"titel": "12-Wochen-Trainingsplan", "preis": 39.0, "bestand": None},
        "p3": {"titel": "Duftproben-Set (Beispiel)", "preis": 14.9, "bestand": 25},
    }

    def list_products(self) -> SkillResult:
        lines = [f"🛍️ Produkte – {TEST_LABEL}", ""]
        lines += [f"- {pid}: {p['titel']} · {p['preis']:.2f} €".replace(".", ",") for pid, p in self.PRODUCTS.items()]
        return SkillResult("shopify", "list_products", "\n".join(lines),
                           [dict(id=pid, **p) for pid, p in self.PRODUCTS.items()])

    def propose_price_change(self, product_id: str = "", new_price: float = 0) -> SkillResult:
        product = self.PRODUCTS.get(str(product_id))
        if product is None:
            raise SkillError("Dieses Produkt gibt es nicht.")
        try:
            price = round(float(new_price), 2)
        except (TypeError, ValueError):
            raise SkillError("Preis bitte als Zahl angeben.") from None
        if not 0 < price <= 10000:
            raise SkillError("Der Preis muss zwischen 0,01 € und 10.000 € liegen.")
        if price == product["preis"]:
            raise SkillError("Der Preis ist bereits so eingestellt.")
        a = self.ctx.gate.propose("shopify_update_product",
                                  {"produkt_id": product_id, "titel": product["titel"], "preis_alt": product["preis"],
                                   "preis_neu": price},
                                  reason="Vorschlag des Skills Shopify",
                                  meta={"beschreibung": f"Preis von „{product['titel']}“ von {product['preis']:.2f} € "
                                                        f"auf {price:.2f} € ändern.",
                                        "konten": ["Shopify-Shop (Testadapter – Ausführung nur simuliert)"],
                                        "daten": [f"Produkt {product_id}: {product['titel']}", "Preisfeld"],
                                        "kosten_eur": 0, "kosten_hinweis": "Preisänderung verändert deinen Umsatz",
                                        "quelle": "Skill shopify"})
        return SkillResult("shopify", "propose_price_change", f"🛍️ Preisänderung vorgeschlagen. Freigabe #{a.id} wartet.",
                           proposal_id=a.id)


# ---------------------------------------------------------------------- Obsidian-Wissensdatenbank
class KnowledgeAdapter(_Adapter):
    label = "Lokal: data/vault (nur nicht vertrauliche Notizen), schreibt nur in 00_Inbox/JARVIS"

    def search(self, query: str = "") -> SkillResult:
        q = self._text(query, "einen Suchbegriff", 200)
        hits = self.ctx.kb.search(q, limit=5)       # vertrauliche Notizen sind ausgeschlossen
        lines = [f"🧠 Wissen zu „{q}“:", ""] + [f"- {h['note'].title}: {h['snippet']}" for h in hits]
        if not hits:
            lines.append("Nichts gefunden (vertrauliche Notizen sind ausgenommen).")
        return SkillResult("knowledge", "search", "\n".join(lines),
                           [{"id": h["note"].id, "titel": h["note"].title} for h in hits], test_data=False)

    def open_goals(self) -> SkillResult:
        goals = self.ctx.kb.open_goals()
        return SkillResult("knowledge", "open_goals", "\n".join(f"- {g}" for g in goals) or "Keine offenen Ziele.",
                           [{"ziel": g} for g in goals], test_data=False)

    def save_note(self, title: str = "", text: str = "") -> SkillResult:
        title = self._text(title, "einen Titel", 80)
        text = self._text(text, "einen Text", 20000)
        path = self.ctx.vault.write_draft(title, text, ["skill"])    # nur 00_Inbox/JARVIS, nie überschreiben
        return SkillResult("knowledge", "save_note", f"📝 Neue Notiz angelegt: {path.name}",
                           [{"datei": path.name}], test_data=False)


# ---------------------------------------------------------------------- Tagesbriefing
class BriefingAdapter(_Adapter):
    label = "Lokal: nutzt nur eingeschaltete Skills"

    def compose(self) -> SkillResult:
        runner = self.ctx.skills
        days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        d = dt.date.today()
        parts = [f"☀️ Tagesbriefing für {days[d.weekday()]}, {d.strftime('%d.%m.%Y')}", ""]
        used = []
        for skill, op, title in (("calendar", "list_today", "📅 Termine"), ("gmail", "list_unread", "📬 E-Mails"),
                                 ("knowledge", "open_goals", "🎯 Offene Ziele")):
            if not runner.is_enabled(skill):
                parts.append(f"{title}: Skill ist aus.")
                continue
            try:
                res = runner.run(skill, op)
            except (SkillBlocked, SkillError) as exc:
                parts.append(f"{title}: nicht verfügbar ({exc}).")
                continue
            used.append(skill)
            body = res.text.split("\n", 2)[-1] if res.text.startswith(("📅", "📬")) else res.text
            parts += [f"{title}:", body.strip() or "–", ""]
        pend = self.ctx.gate.pending()
        parts.append(f"🔐 Warten auf deine Freigabe: {len(pend)}")
        parts.append(f"💶 Budget: {self.ctx.budget.status()}")
        return SkillResult("briefing", "compose", "\n".join(parts), [{"genutzt": s} for s in used],
                           test_data=any(s in ("calendar", "gmail") for s in used))


def build_catalog() -> dict:
    specs = [
        SkillSpec("research", "Internetrecherche", "Sucht Informationen zu deinen Geschäftsbereichen und nennt Quellen.",
                  {"search": Operation("internet.read", "lesen", "Thema recherchieren", ("query",))},
                  ResearchTestAdapter,
                  notes="Später: echte Websuche (kostenpflichtig möglich) – nur nach Freigabe."),
        SkillSpec("gmail", "Gmail", "Liest E-Mails, schreibt Antwort-Entwürfe und schlägt den Versand vor.",
                  {"list_unread": Operation("mail.read", "lesen", "Ungelesene E-Mails anzeigen"),
                   "draft_reply": Operation("mail.draft", "entwurf", "Antwort entwerfen", ("message_id", "text")),
                   "propose_send": Operation("mail.send.propose", "vorschlag", "Versand vorschlagen",
                                             ("to", "subject", "text"))},
                  MailTestAdapter, proposes=("send_email",),
                  notes="Später: Gmail-Verbindung über OAuth – nur nach Freigabe, nur nötigste Rechte."),
        SkillSpec("calendar", "Kalender", "Zeigt Termine und schlägt neue Termine vor.",
                  {"list_today": Operation("calendar.read", "lesen", "Termine heute"),
                   "list_week": Operation("calendar.read", "lesen", "Termine der nächsten 7 Tage"),
                   "propose_event": Operation("calendar.write.propose", "vorschlag", "Termin vorschlagen",
                                              ("title", "date", "time"))},
                  CalendarTestAdapter, proposes=("calendar_write",)),
        SkillSpec("shopify", "Shopify", "Zeigt Produkte und schlägt Änderungen vor.",
                  {"list_products": Operation("shop.read", "lesen", "Produkte anzeigen"),
                   "propose_price_change": Operation("shop.write.propose", "vorschlag", "Preisänderung vorschlagen",
                                                     ("product_id", "new_price"))},
                  ShopTestAdapter, proposes=("shopify_update_product",),
                  notes="Bestellungen und Zahlungen sind grundsätzlich gesperrt."),
        SkillSpec("knowledge", "Obsidian-Wissensdatenbank", "Durchsucht dein Wissen und legt neue Notizen in der Inbox an.",
                  {"search": Operation("vault.read", "lesen", "Wissen durchsuchen", ("query",)),
                   "open_goals": Operation("vault.read", "lesen", "Offene Ziele"),
                   "save_note": Operation("vault.inbox.write", "entwurf", "Neue Notiz in 00_Inbox/JARVIS",
                                          ("title", "text"))},
                  KnowledgeAdapter),
        SkillSpec("briefing", "Tagesbriefing", "Fasst Termine, E-Mails, Ziele und offene Freigaben zusammen.",
                  {"compose": Operation("briefing.compose", "lesen", "Briefing erstellen")},
                  BriefingAdapter, notes="Nutzt nur Skills, die du eingeschaltet hast."),
    ]
    return {s.id: s for s in specs}


CATALOG = build_catalog()
