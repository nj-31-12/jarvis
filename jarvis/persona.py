"""Persönlichkeit von JARVIS.

Die Systemanweisung liegt als lesbare Markdown-Datei in config/persona.md, damit
du sie selbst anpassen kannst. Sobald ein echtes Sprachmodell angebunden ist
(Phase 3, über Hermes), wird dieser Text als Systemanweisung mitgegeben.
Die Sicherheitsregeln hängen NICHT von diesem Text ab – sie sind im Code erzwungen.
"""
from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT

PERSONA_FILE = PROJECT_ROOT / "config" / "persona.md"


def load_persona(path: str | Path | None = None) -> str:
    path = Path(path) if path else PERSONA_FILE
    return path.read_text(encoding="utf-8") if path.exists() else "Du bist JARVIS, ein sachlicher Assistent."


def build_system_prompt(cfg: dict, mode: str = "text") -> str:
    """Setzt Persönlichkeit, Geschäftsbereiche und Ausgabeform zusammen."""
    areas = "\n".join(f"- {a}" for a in cfg.get("business_areas", []))
    style = ("Antworte in gut sprechbaren, kurzen Sätzen ohne Tabellen und ohne Emojis."
             if mode == "voice" else "Nutze Markdown sparsam: kurze Absätze, Listen nur wenn hilfreich.")
    return f"{load_persona()}\n\n## Geschäftsbereiche deines Nutzers\n{areas}\n\n## Ausgabeform\n{style}\n"
