"""Konfiguration und Geheimnisse laden.

- Normale Einstellungen: config/jarvis.json (darf ins Git).
- Geheimnisse (Tokens, Schlüssel): .env-Datei oder Umgebungsvariablen (niemals ins Git).
"""
from __future__ import annotations

import copy
import json
import os
import stat
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "timezone": "Europe/Berlin",
    "quiet_hours": {"start": "22:00", "end": "07:00"},
    "briefing_time": "07:00",
    "approval_ttl_minutes": 60,
    "budget": {"daily_eur": 1.00, "monthly_eur": 15.00},
    "data_dir": "data",
    "vault_dir": "data/vault",
    # Ordner im Vault, in die JARVIS OHNE Freigabe schreiben darf (nur eigene Entwürfe).
    "vault_auto_write_dirs": ["00_Inbox/JARVIS"],
    # Nur diese Themen darf JARVIS nachts selbstständig recherchieren.
    "research_topics": [
        "Shopify-Trends",
        "Affiliate-Programme im Fitness-Bereich",
        "KI-Automatisierung für kleine Online-Shops",
    ],
    # Alle Geschäftsbereiche. Die Nachtrecherche rotiert, damit keiner vernachlässigt wird.
    "business_areas": [
        "NYoung.Coaching",
        "Fitness und Ernährungsberatung",
        "Community-Management",
        "Shopify und E-Commerce",
        "Scent Edit und Parfüm-Affiliate-Marketing",
        "Social Media und Content-Produktion",
        "KI-Automatisierung",
        "Webdesign und Softwareentwicklung",
        "Automobilbranche und Fahrzeughandel",
        "Neue digitale Geschäftsmodelle",
        "Unternehmensführung und Organisation",
        "Weiterbildung und persönliche Entwicklung",
        "Young Living Network-Marketing",
    ],
    "night_topics_per_run": 3,
    # Business-Gedächtnis (Phase 2, Schritt 4): liest NUR data/vault
    "knowledge": {
        "private_dirs": ["90_Privat"],
        # Hier z. B. den Namen deines Ausbildungsbetriebs eintragen: Notizen damit werden automatisch vertraulich
        "confidential_terms": [],
        "max_note_kb": 1024,
        "max_notes": 2000,
    },
    # Datenschutz für eine SPÄTERE externe KI-Anbindung (Version 4.2). Standard: nichts verlässt den Rechner.
    "privacy": {
        "external_ai_allowed": False,
        "max_chars_external": 12000,
    },
    # KI-Modelle (Version 5). Standard: nur das eingebaute Testmodell. Jedes weitere Modell braucht einen Eintrag
    # unter "models" mit Freigabe, Datenschutzprüfung und dem NAMEN der Schlüssel-Variable (Schlüssel nur in .env).
    "ai": {
        "active_model": "mock",
        "models": {},
    },
    # Betrieb (Version 5, Phase D). "lokal" = MacBook. "server" = eigener Linux-Server: strengere Prüfungen beim Start.
    "server": {"mode": "lokal", "min_free_mb": 500, "backup_max_age_hours": 48},
    # Aufgabenplaner (Version 5, Phase E). "test": Ergebnisse nur in data/aufgaben-test/, keine Meldungen.
    # "aktiv": neue Notizen in 00_Inbox/JARVIS + Meldung. Externe Aktionen nie – höchstens Vorschläge.
    "scheduler": {"mode": "test"},
    # Sicherungen: eigener Ordner außerhalb von data/ (relativ zum Projektordner oder absolut)
    "backup": {"dir": "sicherungen"},
    # Browseroberfläche (Phase 2). Nur auf diesem Rechner erreichbar; Freigaben im Browser standardmäßig AUS.
    "web": {
        "host": "127.0.0.1",
        "port": 8765,
        "session_minutes": 30,
        "approvals_enabled": False,
        "users": [],
    },
    # Sprache (vorbereitet, noch ohne echte Stimme)
    "voice": {"tts": "stumm", "stt": "aus", "profile": "erzähler",
              "description": "ruhig, tief, natürlich, souverän und intelligent"},
    # Begriffe, die in keiner Aktion vorkommen dürfen (Bank, Ausbildungsbetrieb ...).
    "forbidden_terms": ["iban", "bic", "onlinebanking", "pin", "tan", "kreditkarte"],
    "telegram": {"allowed_user_ids": [], "approval_chat_id": None},
    # Stand 23: Webseiten-Werkstatt. Websuche + Webseiten-Check erst nach `python3 -m jarvis werkstatt-an`.
    "werkstatt": {"web_research_allowed": False, "output_dir": "~/JARVIS/websites", "max_betriebe": 5,
                  "max_suchen": 4, "max_eur_pro_suche": 0.15},
}

SECRET_KEYS = ("JARVIS_APPROVAL_SECRET", "TELEGRAM_BOT_TOKEN")


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


# Version 5: Pfade per Umgebungsvariable überschreibbar (für einen Server mit getrennten Ordnern)
ENV_CONFIG, ENV_DATA_DIR, ENV_VAULT_DIR, ENV_BACKUP_DIR, ENV_FILE = (
    "JARVIS_CONFIG", "JARVIS_DATA_DIR", "JARVIS_VAULT_DIR", "JARVIS_BACKUP_DIR", "JARVIS_ENV_FILE")


def load_config(path: str | os.PathLike | None = None) -> dict:
    if path is None and os.environ.get(ENV_CONFIG):
        path = os.environ[ENV_CONFIG]
    path = Path(path) if path else PROJECT_ROOT / "config" / "jarvis.json"
    if os.environ.get(ENV_CONFIG) and not path.exists():
        # Ausdrücklich angegebene Datei fehlt: NICHT still mit Standardwerten weiterarbeiten
        raise ValueError(f"Konfigurationsdatei {path} (aus {ENV_CONFIG}) nicht gefunden.")
    cfg = copy.deepcopy(DEFAULTS)
    if path.exists():
        try:
            user_cfg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Die Konfigurationsdatei {path} ist kein gültiges JSON ({exc}). "
                             f"Bitte die letzte Änderung rückgängig machen oder config/jarvis.example.json "
                             f"als Vorlage nehmen.") from exc
        if not isinstance(user_cfg, dict):
            raise ValueError(f"Die Konfigurationsdatei {path} muss ein JSON-Objekt {{…}} enthalten.")
        cfg = _deep_merge(cfg, user_cfg)
    if cfg["web"].get("host") not in ("127.0.0.1", "localhost", "::1"):
        # Sicherheitsbremse: Ohne HTTPS und ohne gesicherten Tunnel darf die Oberfläche nicht ins Netz.
        raise ValueError("web.host darf in Phase 2 nur 127.0.0.1 sein (siehe docs/08_Phase2_Schritt1.md).")
    from .ai_models import validate_ai_config
    validate_ai_config(cfg)          # bricht ab, wenn ein API-Schlüssel in der Konfiguration steht
    for key, env in (("data_dir", ENV_DATA_DIR), ("vault_dir", ENV_VAULT_DIR)):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    if os.environ.get(ENV_BACKUP_DIR):
        cfg["backup"] = dict(cfg.get("backup") or {}, dir=os.environ[ENV_BACKUP_DIR])
    for key in ("data_dir", "vault_dir"):
        p = Path(cfg[key]).expanduser()
        cfg[key] = str(p if p.is_absolute() else PROJECT_ROOT / p)
    b = Path(str((cfg.get("backup") or {}).get("dir") or "sicherungen")).expanduser()
    cfg["backup"] = dict(cfg.get("backup") or {}, dir=str(b if b.is_absolute() else PROJECT_ROOT / b))
    if (cfg.get("scheduler") or {}).get("mode", "test") not in ("test", "aktiv"):
        raise ValueError('scheduler.mode muss "test" oder "aktiv" sein.')
    if cfg.get("server", {}).get("mode") not in ("lokal", "server"):
        raise ValueError('server.mode muss "lokal" oder "server" sein.')
    return cfg


def load_secrets(env_file: str | os.PathLike | None = None) -> dict:
    """Liest Geheimnisse aus .env (falls vorhanden) und Umgebungsvariablen.

    Umgebungsvariablen haben Vorrang. Warnt, wenn die .env-Datei für andere lesbar ist.
    """
    if env_file is None and os.environ.get(ENV_FILE):
        env_file = os.environ[ENV_FILE]
    env_file = Path(env_file) if env_file else PROJECT_ROOT / ".env"
    secrets: dict[str, str] = {}
    if env_file.exists():
        mode = env_file.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            print(f"WARNUNG: {env_file} ist für andere Benutzer lesbar. Bitte: chmod 600 .env")
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip().strip('"').strip("'")
    # Version 5: systemd-Zugangsdaten (LoadCredential=…): je Geheimnis eine Datei, nur für diesen Dienst lesbar
    cred_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if cred_dir and Path(cred_dir).is_dir():
        for f in sorted(Path(cred_dir).iterdir()):
            if f.is_file() and is_secret_name(f.name):
                secrets[f.name] = f.read_text(encoding="utf-8").strip()
    for key in SECRET_KEYS:
        if os.environ.get(key):
            secrets[key] = os.environ[key]
    # Schlüssel externer KI-Modelle (Name muss mit JARVIS_ beginnen, siehe ai_models.py)
    for key, value in os.environ.items():
        if key.startswith("JARVIS_") and key.endswith("_KEY") and value:
            secrets[key] = value
    return secrets


def is_secret_name(name: str) -> bool:
    import re as _re
    return name in SECRET_KEYS or bool(_re.fullmatch(r"JARVIS_[A-Z0-9_]{2,60}", name))
