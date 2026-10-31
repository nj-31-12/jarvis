"""Skill-System (Version 5, Phase C).

Ein Skill ist eine klar begrenzte Fähigkeit von JARVIS (z. B. „Kalender lesen“).

Regeln, die der Code erzwingt:
  1. Jeder Skill ist anfangs AUS. Einschalten und Berechtigungen erweitern geht NUR über die
     Freigabezentrale (Aktion enable_skill bzw. grant_permission, mit deiner Genehmigung).
  2. Ausschalten geht jederzeit sofort und ohne Freigabe.
  3. Jede Operation braucht genau eine benannte Berechtigung. Fehlt sie: blockiert und protokolliert.
  4. Lesen und Entwürfe passieren direkt. Alles, was nach außen geht oder etwas verändert, wird nur als
     Aktion VORGESCHLAGEN und wartet in der Freigabezentrale.
  5. Zurzeit gibt es ausschließlich Testadapter mit erfundenen Daten. Sie bauen keine
     Netzwerkverbindung auf und verbinden kein Konto.
"""
from .base import (PERMISSIONS, SkillBlocked, SkillError, SkillResult, SkillRunner, SkillSpec, SkillState)
from .catalog import CATALOG, build_catalog

__all__ = ["PERMISSIONS", "SkillBlocked", "SkillError", "SkillResult", "SkillRunner", "SkillSpec", "SkillState",
           "CATALOG", "build_catalog"]
