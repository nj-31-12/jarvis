"""JARVIS-Kern: verbindet alle Bausteine und beantwortet Befehle.

Wichtig für die Sicherheit: Das Sprachmodell (self.llm) liefert hier nur TEXT.
Ausführende Aktionen entstehen ausschließlich über self.gate.propose(...) und
werden erst nach einer gültigen, signierten Freigabe ausgeführt (Telegram oder –
falls ausdrücklich eingeschaltet – Browser mit zweitem Faktor).
"""
from __future__ import annotations

import datetime as dt
import secrets
from pathlib import Path

from .actions_sim import make_handlers
from .approval import ApprovalGate
from .audit import AuditLog
from .config import PROJECT_ROOT
from .ai_providers.anthropic import AIServiceError
from .budget import BudgetGuard, BudgetExceeded
from .killswitch import KillSwitch, KillSwitchActive
from .llm import LLMRouter
from .notify import Notifier, console_channel
from .knowledge import KnowledgeBase
from .obsidian import Vault
from .persona import build_system_prompt
from .policy import PolicyViolation
from .rotation import TopicRotation

HELP = """🤖 JARVIS – Befehle
/idee <Text> – Geschäftsidee analysieren (Entwurf in Obsidian)
/post <Thema> – Social-Media-Post entwerfen + Veröffentlichung zur Freigabe
/mail <an> | <Betreff> | <Text> – E-Mail vorbereiten (nur mit Freigabe)
/notiz <Text> – Notiz in Obsidian-Inbox speichern
/strategie <Idee> – Geschäftsidee durch 11 Experten-Brillen prüfen (landet im Second Brain)
/suche <Begriff> – im Wissensspeicher suchen (ohne vertrauliche Notizen)
/wissen <Thema> – was JARVIS zu einem Thema weiß, mit Quellen
/profile – Stand der Profile deiner Geschäftsbereiche
/ziel <Text> – Ziel als Vorschlag speichern
/briefing – Tagesbriefing jetzt anzeigen
/nacht – Nachtrecherche jetzt simulieren
/offen – offene Freigaben anzeigen
/skills – Skills und ihr Status (Einschalten nur über die Freigabezentrale)
/bereiche – welche Geschäftsbereiche wie oft recherchiert wurden
/status – Systemstatus
/stop – NOTABSCHALTUNG (Aufheben nur lokal am Rechner)"""


class Jarvis:
    def __init__(self, cfg: dict, secrets_: dict, channel=console_channel, clock=None):
        self.cfg = cfg
        data = Path(cfg["data_dir"])
        data.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLog(data / "audit.jsonl")
        self.kill = KillSwitch(data)
        self.budget = BudgetGuard(data / "budget.db", cfg["budget"]["daily_eur"], cfg["budget"]["monthly_eur"])
        from .ai_models import ModelPolicy, make_model
        from .outbound import OutboundGuard
        # Version 5: zentrale Erlaubnisliste. Unbekannte Modelle sind gesperrt; Schlüssel nur aus .env.
        self.llm = LLMRouter(self.budget, self.kill, model=make_model(cfg),
                             guard=OutboundGuard(cfg, self.audit),
                             policy=ModelPolicy(cfg, self.audit, secrets_))
        self.vault = Vault(cfg["vault_dir"], cfg["vault_auto_write_dirs"])
        self.vault.init(PROJECT_ROOT / "vault-vorlage")
        kcfg = cfg.get("knowledge", {})
        # Nur-Lese-Zugriff mit Vertraulichkeitsregeln. Gilt für Suche, Chat-Kontext, Quellen und Briefing.
        self.kb = KnowledgeBase(cfg["vault_dir"], private_dirs=kcfg.get("private_dirs", ["90_Privat"]),
                                confidential_terms=kcfg.get("confidential_terms", []),
                                max_note_bytes=int(kcfg.get("max_note_kb", 1024)) * 1024,
                                max_notes=int(kcfg.get("max_notes", 2000)))
        self.vault.on_write = self.kb.invalidate
        tg = cfg["telegram"]
        web = cfg.get("web", {})
        secret = secrets_.get("JARVIS_APPROVAL_SECRET") or _local_secret(data)
        self.gate = ApprovalGate(data / "actions.db", secret, self.audit, self.kill,
                                 allowed_user_ids=tg["allowed_user_ids"],
                                 approval_chat_id=tg.get("approval_chat_id"),
                                 ttl_minutes=cfg["approval_ttl_minutes"],
                                 forbidden_terms=cfg["forbidden_terms"],
                                 web_approvals_enabled=web.get("approvals_enabled", False),
                                 allowed_web_users=web.get("users", []))
        self.rotation = TopicRotation(data / "rotation.db")
        # Systemanweisung für ein späteres echtes Sprachmodell (das simulierte Modell ignoriert sie).
        self.system_prompt = build_system_prompt(cfg)
        for action_type, fn in make_handlers(data / "sandbox").items():
            self.gate.register_handler(action_type, fn)
        # Version 5: Skills. Alle starten AUS; Einschalten nur über die Freigabezentrale.
        from .skills import CATALOG, SkillRunner, SkillState
        self.skills = SkillRunner(CATALOG, SkillState(data / "skills.db", self.audit), self, self.audit, self.kill)
        self.gate.register_handler("enable_skill", self.skills.handle_enable)
        self.gate.register_handler("grant_permission", self.skills.handle_grant)
        # Version 5: Aufgabenplaner (Standard: Testmodus)
        from .scheduler import Scheduler
        self.scheduler = Scheduler(self, data / "tasks.db", mode=(cfg.get("scheduler") or {}).get("mode", "test"))
        self.notifier = Notifier(data / "notify.db", cfg["quiet_hours"]["start"], cfg["quiet_hours"]["end"],
                                 cfg["timezone"], channel, clock=clock)

    # ------------------------------------------------------------------ Eingang
    def handle_text(self, text: str) -> str:
        text = (text or "").strip()
        self.audit.write("message_in", length=len(text), command=text.split(" ", 1)[0] if text.startswith("/") else None)
        if text.startswith("/stop"):
            self.kill.activate("Telegram /stop")
            self.audit.write("killswitch_on", source="telegram")
            return "🛑 Notabschaltung aktiv. JARVIS führt nichts mehr aus.\nAufheben nur lokal: python3 -m jarvis resume"
        if self.kill.is_active() and not text.startswith(("/status", "/hilfe", "/start")):
            return "🛑 Notabschaltung aktiv. Nur /status ist verfügbar."
        cmd, _, arg = text.partition(" ")
        arg = arg.strip()
        try:
            if cmd in ("/start", "/hilfe", "/help"):
                return HELP
            if cmd == "/idee":
                return self.analyze_idea(arg) if arg else "Bitte so: /idee Fitness-Rezepte als E-Book"
            if cmd == "/post":
                return self.prepare_post(arg) if arg else "Bitte so: /post 5 Fehler beim Muskelaufbau"
            if cmd == "/mail":
                return self.prepare_mail(arg)
            if cmd == "/strategie":
                from .strategy import run_strategy
                msg, path, analysis = run_strategy(self, arg)
                return f"{msg}\n\n{analysis}" if path else msg
            if cmd == "/notiz":
                p = self.vault.write_draft(arg[:60] or "Notiz", arg, ["notiz"])
                return f"📝 Gespeichert: {p.name}"
            if cmd == "/ziel":
                p = self.vault.write_draft(f"Zielvorschlag {arg[:40]}", f"- [ ] {arg}", ["ziel"])
                return f"🎯 Zielvorschlag gespeichert ({p.name}). Verschiebe ihn in Obsidian nach 01_Ziele, wenn er gilt."
            if cmd == "/wissen":
                return self.knowledge_answer(arg) if arg else "Bitte so: /wissen Scent Edit"
            if cmd == "/profile":
                return self.profiles_overview()
            if cmd == "/suche":
                # Vertrauliche Notizen werden nie angezeigt (Schritt 4); früher: vault.search über alles
                hits = [(h["note"].relpath, h["snippet"]) for h in self.kb.search(arg, limit=5)]
                return "\n\n".join(f"📄 {f}\n…{s}…" for f, s in hits) or "Nichts gefunden."
            if cmd == "/briefing":
                return self.morning_briefing()
            if cmd == "/nacht":
                return self.night_research()
            if cmd == "/bereiche":
                cov = self.rotation.coverage(self.research_pool())
                return "📊 Recherche-Abdeckung (Anzahl Läufe):\n" + "\n".join(f"• {t}: {n}" for t, n in cov.items())
            if cmd == "/skills":
                return self.skills_overview()
            if cmd == "/offen":
                pend = self.gate.pending()
                return "\n\n".join(a.summary() for a in pend) or "Keine offenen Freigaben."
            if cmd == "/status":
                return self.status()
            if cmd.startswith("/"):
                return "Unbekannter Befehl. /hilfe zeigt alle Befehle."
            return self.llm.complete("chat", text)
        except (BudgetExceeded, KillSwitchActive, PolicyViolation, PermissionError) as exc:
            self.audit.write("refused", reason=str(exc))
            return f"⛔ {exc}"
        except AIServiceError as exc:          # Meldung enthält nie Inhalte
            self.audit.write("ai_service_error", reason=str(exc)[:200])
            return f"⚠️ {exc}"

    def handle_voice(self, duration_s: int) -> str:
        return (f"🎙️ Sprachnachricht ({duration_s}s) empfangen.\n"
                "Transkription ist im Prototyp noch aus. In Phase 2 übernimmt das Hermes "
                "(Whisper – lokal kostenlos oder per API).")

    # ------------------------------------------------------------------ Funktionen
    def analyze_idea(self, idea: str) -> str:
        analysis = self.llm.complete("idea", idea)
        p = self.vault.write_draft(f"Idee {idea[:50]}", analysis, ["geschäftsidee"])
        return f"💡 Analyse erstellt und in Obsidian gespeichert: {p.name}\n\n{_shorten(analysis, 1500)}"

    def prepare_post(self, topic: str) -> str:
        draft = self.llm.complete("post", topic)
        self.vault.write_draft(f"Post {topic[:50]}", draft, ["content"])
        action = self.gate.propose("publish_post", {"plattform": "Instagram", "text": draft},
                                   reason=f"Post zum Thema '{topic}'",
                                   meta={"beschreibung": f"Instagram-Beitrag zum Thema „{topic[:80]}“ veröffentlichen.",
                                         "konten": ["Instagram (noch nicht verbunden – Ausführung wird nur simuliert)"],
                                         "daten": [f"Beitragstext ({len(draft)} Zeichen)",
                                                   "Entwurf in Obsidian 00_Inbox/JARVIS"],
                                         "kosten_eur": 0, "kosten_hinweis": "keine Werbung, keine Kosten",
                                         "quelle": "Befehl /post"})
        self.request_approval(action)
        return f"✍️ Entwurf erstellt. Freigabe-Anfrage #{action.id} wurde gesendet."

    def prepare_mail(self, arg: str) -> str:
        parts = [p.strip() for p in arg.split("|")]
        if len(parts) != 3 or not all(parts):
            return "Bitte so: /mail max@beispiel.de | Betreff | Nachricht"
        action = self.gate.propose("send_email", {"an": parts[0], "betreff": parts[1], "text": parts[2]},
                                   reason="E-Mail auf deinen Wunsch",
                                   meta={"beschreibung": f"E-Mail an {parts[0][:120]} senden.",
                                         "konten": ["E-Mail-Konto (noch nicht verbunden – Ausführung wird nur simuliert)"],
                                         "daten": [f"Empfänger: {parts[0][:120]}", f"Betreff: {parts[1][:120]}",
                                                   f"Nachricht ({len(parts[2])} Zeichen)"],
                                         "kosten_eur": 0, "quelle": "Befehl /mail"})
        self.request_approval(action)
        return f"📧 E-Mail vorbereitet. Freigabe-Anfrage #{action.id} wurde gesendet."

    def request_approval(self, action) -> str:
        buttons = [[("✅ Freigeben", self.gate.callback_data("ok", action.id)),
                    ("❌ Ablehnen", self.gate.callback_data("no", action.id))]]
        return self.notifier.notify("🔐 FREIGABE NÖTIG\n\n" + action.summary(), "urgent", buttons,
                                    action_id=action.id)

    def on_button(self, data: str, from_user_id: int, chat_id: int) -> str:
        """Telegram-Button."""
        ok, msg = self.gate.handle_callback(data, from_user_id, chat_id)
        if not ok:
            return f"⛔ {msg}"
        decision, action_id, _ = data.split(":", 2)
        return self._after_decision(decision, action_id)

    def on_web_decision(self, decision: str, action_id: str, token: str, web_user: str,
                        session_id: str, second_factor_ok: bool, shown_hash: str | None = None) -> str:
        """Browser-Entscheidung. Genehmigen nur mit web.approvals_enabled = true, Passwort und angezeigter Fassung."""
        ok, msg = self.gate.handle_web_decision(decision, action_id, token, web_user, session_id, second_factor_ok,
                                                shown_hash=shown_hash)
        if not ok:
            return f"⛔ {msg}"
        return self._after_decision(decision, action_id)

    def _after_decision(self, decision: str, action_id: str) -> str:
        if decision != "ok":
            return f"❌ Aktion #{action_id} abgelehnt."
        try:
            return f"✅ {self.gate.execute(action_id)}"
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ Ausführung fehlgeschlagen: {exc}"

    def research_pool(self) -> list[str]:
        return list(dict.fromkeys(self.cfg["research_topics"] + self.cfg.get("business_areas", [])))

    def knowledge_answer(self, topic: str) -> str:
        hits = self.kb.search(topic, limit=5)
        if not hits:
            return f"Zu „{topic}“ habe ich noch nichts in deinem Wissen gefunden (vertrauliche Notizen sind ausgenommen)."
        lines = [f"🧠 Das weiß ich zu „{topic}“:", ""]
        for h in hits:
            lines.append(f"- **{h['note'].title}** ({h['note'].relpath}): {h['snippet']}")
        return "\n".join(lines)

    def skills_overview(self) -> str:
        lines = ["🧩 Skills (alle mit Testadapter, ohne Kontoverbindung):", ""]
        for row in self.skills.overview():
            spec = row["spec"]
            state = "⛔ gesperrt" if row["blocked"] else ("🟢 an" if row["enabled"] else "⚪ aus")
            lines.append(f"- {state} **{spec.name}** ({spec.id}) – {spec.description}")
        lines += ["", "Einschalten: Browser → Skills → „Aktivierung beantragen“, dann in der Freigabezentrale genehmigen."]
        return "\n".join(lines)

    def profiles_overview(self) -> str:
        from .profiles import profile_status
        icons = {"fehlt": "○", "Entwurf": "◐", "übernommen": "●"}
        lines = ["📁 Bereichsprofile (● übernommen · ◐ Entwurf in der Inbox · ○ fehlt):", ""]
        for e in profile_status(self.kb):
            p = e["project"]
            lines.append(f"- {icons[e['state']]} **{p['name']}** · Status: {p['status']} · Profil: {e['state']}")
        return "\n".join(lines)

    def night_research(self) -> str:
        """Recherchiert die am längsten vernachlässigten Themen (Rotation über alle Bereiche)."""
        topics = self.rotation.pick(self.research_pool(), int(self.cfg.get("night_topics_per_run", 3)))
        done = []
        for topic in topics:
            result = self.llm.complete("research", topic)
            p = self.vault.write_draft(f"Recherche {topic}", result, ["recherche", "nacht"])
            self.rotation.mark_done(topic)
            done.append(p.name)
            self.notifier.notify(f"🌙 Nachtrecherche fertig: {topic}", "normal")
        self.audit.write("night_research", topics=topics)
        return "Nachtrecherche abgeschlossen:\n" + "\n".join(f"• {d}" for d in done)

    def morning_briefing(self) -> str:
        days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        d = dt.date.today()
        today = f"{days[d.weekday()]}, {d.strftime('%d.%m.%Y')}"
        queued = self.notifier.drain_queue()
        goals = self.kb.open_goals()          # ohne vertrauliche Ziel-Notizen
        pend = self.gate.pending()
        inbox = self.vault.list_notes("00_Inbox/JARVIS")[-5:]
        lines = [f"☀️ Guten Morgen! Briefing für {today}", ""]
        lines.append("🌙 Über Nacht:")
        lines += [f"  • {q}" for q in queued] or ["  • nichts Neues"]
        lines.append("\n🎯 Offene Ziele:")
        lines += [f"  • {g}" for g in goals[:5]] or ["  • Noch keine – lege welche in 01_Ziele an."]
        lines.append("\n🔐 Warten auf deine Freigabe:")
        lines += [f"  • #{a.id} {a.action_type}" for a in pend] or ["  • keine"]
        lines.append("\n📝 Neue Entwürfe in Obsidian:")
        lines += [f"  • {p.stem}" for p in inbox] or ["  • keine"]
        lines.append(f"\n💶 Budget: {self.budget.status()}")
        return "\n".join(lines)

    def close(self) -> None:
        """Alle Datenbanken schließen (beim Beenden)."""
        for part in (self.gate, self.budget, self.notifier, self.rotation, self.skills.state, self.scheduler):
            part.close()

    def status(self) -> str:
        ok, msg = self.audit.verify()
        return (f"⚙️ JARVIS Status\n"
                f"Notabschaltung: {'AKTIV 🛑' if self.kill.is_active() else 'aus ✅'}\n"
                f"Nachtruhe gerade: {'ja 🌙' if self.notifier.quiet_now() else 'nein'}\n"
                f"Offene Freigaben: {len(self.gate.pending())}\n"
                f"Wartende Meldungen: {self.notifier.queued_count()}\n"
                f"Budget: {self.budget.status()}\n"
                f"Protokoll: {msg}\n"
                f"Modell: {self.llm.model.name} "
                f"({'simuliert' if getattr(self.llm.model, 'is_test_mode', False) else 'nur mit Freigabe'})")


def _shorten(text: str, limit: int) -> str:
    """Kürzt an einer Zeilengrenze statt mitten im Wort (Telegram erlaubt max. 4.096 Zeichen)."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    return text[:cut if cut > 0 else limit].rstrip() + "\n\n… (vollständig in der Obsidian-Notiz)"


def _local_secret(data_dir: Path) -> str:
    """Für lokale Tests: erzeugt einmalig ein zufälliges Geheimnis in data/.approval_secret."""
    path = data_dir / ".approval_secret"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        path.chmod(0o600)
    return path.read_text(encoding="utf-8").strip()
